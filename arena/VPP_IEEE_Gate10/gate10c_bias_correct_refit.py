from pathlib import Path
import json

import numpy as np
import pandas as pd

from scipy import stats
from scipy.optimize import minimize
from scipy.special import gammaln


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

CAL = ROOT / "data" / "calibration"
REPORTS = ROOT / "reports"

INPUT = CAL / "joint_residual_database_hourly.csv"

OUTPUT_CORRECTED = (
    CAL / "joint_residual_database_hourly_bias_corrected.csv"
)

BIAS_REPORT = (
    REPORTS / "gate10c_bias_correction.json"
)

COPULA_REPORT = (
    REPORTS / "gate10c_refit_bias_corrected.json"
)

GAUSSIAN_CORR = (
    CAL / "gaussian_copula_correlation_bias_corrected.csv"
)

STUDENT_CORR = (
    CAL / "student_t_copula_correlation_bias_corrected.csv"
)


VARIABLES = [
    "price_error",
    "load_error",
    "wind_on_error",
    "wind_off_error",
    "pv_error",
]

D = len(VARIABLES)

EPS = 1e-6
MIN_DF = 2.05
MAX_DF = 80.0


# ============================================================
# LOAD
# ============================================================

def load_data():

    if not INPUT.exists():
        raise FileNotFoundError(INPUT)

    df = pd.read_csv(INPUT)

    required = [
        "timestamp",
        "period",
        *VARIABLES
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns: {missing}"
        )

    df["timestamp"] = (
        pd.to_datetime(
            df["timestamp"],
            utc=True,
            errors="coerce"
        )
        .dt.tz_convert("Europe/Berlin")
    )

    for col in VARIABLES:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    return (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


# ============================================================
# BIAS CORRECTION
# ============================================================

def bias_correct(df):

    train = df[
        df["period"] == "TRAIN"
    ].copy()

    if train.empty:
        raise ValueError(
            "TRAIN dataset is empty."
        )

    biases = {}

    corrected = df.copy()

    for col in VARIABLES:

        mu = float(
            train[col]
            .dropna()
            .mean()
        )

        biases[col] = mu

        corrected[
            f"{col}_bc"
        ] = corrected[col] - mu

    return corrected, biases


# ============================================================
# EMPIRICAL MARGINALS
# ============================================================

def fit_marginals(train):

    marginals = {}

    for col in VARIABLES:

        x = (
            train[f"{col}_bc"]
            .dropna()
            .to_numpy(float)
        )

        marginals[col] = np.sort(x)

    return marginals


def empirical_u(values, sorted_train):

    values = np.asarray(
        values,
        dtype=float
    )

    n = len(sorted_train)

    ranks = np.searchsorted(
        sorted_train,
        values,
        side="right"
    )

    u = (
        ranks + 0.5
    ) / (n + 1.0)

    return np.clip(
        u,
        EPS,
        1.0 - EPS
    )


def to_uniform(
    df,
    marginals
):

    u = np.zeros(
        (len(df), D)
    )

    for j, col in enumerate(VARIABLES):

        u[:, j] = empirical_u(
            df[f"{col}_bc"].to_numpy(float),
            marginals[col]
        )

    return u


# ============================================================
# GAUSSIAN COPULA
# ============================================================

def nearest_pd(matrix):

    matrix = (
        matrix + matrix.T
    ) / 2.0

    eigvals, eigvecs = np.linalg.eigh(
        matrix
    )

    eigvals = np.maximum(
        eigvals,
        1e-8
    )

    out = (
        eigvecs
        @ np.diag(eigvals)
        @ eigvecs.T
    )

    d = np.sqrt(
        np.diag(out)
    )

    out = (
        out
        / np.outer(d, d)
    )

    np.fill_diagonal(
        out,
        1.0
    )

    return out


def gaussian_corr(u):

    z = stats.norm.ppf(u)

    return nearest_pd(
        np.corrcoef(
            z,
            rowvar=False
        )
    )


def gaussian_ll(u, corr):

    z = stats.norm.ppf(u)

    sign, logdet = np.linalg.slogdet(
        corr
    )

    if sign <= 0:
        return -np.inf

    inv = np.linalg.inv(corr)

    q = np.einsum(
        "ni,ij,nj->n",
        z,
        inv,
        z
    )

    z2 = np.sum(
        z**2,
        axis=1
    )

    return float(
        -0.5 * len(z) * logdet
        -0.5 * np.sum(q - z2)
    )


# ============================================================
# STUDENT-T COPULA
# ============================================================

def student_t_ll(
    u,
    df_t,
    corr
):

    if not (
        MIN_DF < df_t <= MAX_DF
    ):
        return -np.inf

    corr = nearest_pd(corr)

    x = stats.t.ppf(
        u,
        df=df_t
    )

    sign, logdet = np.linalg.slogdet(
        corr
    )

    if sign <= 0:
        return -np.inf

    inv = np.linalg.inv(corr)

    q = np.einsum(
        "ni,ij,nj->n",
        x,
        inv,
        x
    )

    n, d = x.shape

    const_mv = (
        gammaln((df_t + d) / 2)
        - gammaln(df_t / 2)
        - 0.5 * d * np.log(
            df_t * np.pi
        )
        - 0.5 * logdet
    )

    log_mv = (
        n * const_mv
        - (df_t + d) / 2
        * np.sum(
            np.log1p(q / df_t)
        )
    )

    log_uni = np.sum(
        stats.t.logpdf(
            x,
            df=df_t
        )
    )

    return float(
        log_mv - log_uni
    )


def fit_student_t(
    u,
    corr
):

    starts = [
        3.0,
        5.0,
        10.0,
        20.0,
        40.0
    ]

    best = None

    for start in starts:

        def objective(x):

            df_t = (
                np.exp(x[0])
                + MIN_DF
            )

            ll = student_t_ll(
                u,
                df_t,
                corr
            )

            if not np.isfinite(ll):
                return 1e100

            return -ll

        result = minimize(
            objective,
            x0=[
                np.log(
                    start - MIN_DF
                )
            ],
            method="L-BFGS-B",
            bounds=[
                (
                    np.log(0.01),
                    np.log(
                        MAX_DF - MIN_DF
                    )
                )
            ],
        )

        df_candidate = (
            np.exp(result.x[0])
            + MIN_DF
        )

        ll = -result.fun

        candidate = {
            "df": float(df_candidate),
            "loglik": float(ll),
            "success": bool(
                result.success
            ),
        }

        if (
            best is None
            or ll > best["loglik"]
        ):
            best = candidate

    return best


# ============================================================
# AIC
# ============================================================

def aic(loglik, k):

    return float(
        2 * k - 2 * loglik
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10C.1 — BIAS CORRECTION + COPULA REFIT")
    print("==============================================\n")

    df = load_data()

    print(
        f"Loaded rows: {len(df):,}"
    )

    # --------------------------------------------------------
    # Bias correction
    # --------------------------------------------------------

    corrected, biases = bias_correct(df)

    print("\n----------------------------------------------")
    print("TRAIN BIAS VALUES")
    print("----------------------------------------------")

    for col, value in biases.items():

        print(
            f"{col:20s}: "
            f"{value:.6f}"
        )

    # --------------------------------------------------------
    # Verify TRAIN means after correction
    # --------------------------------------------------------

    print("\n----------------------------------------------")
    print("CORRECTED TRAIN MEANS")
    print("----------------------------------------------")

    train_corrected = corrected[
        corrected["period"] == "TRAIN"
    ]

    corrected_means = {}

    for col in VARIABLES:

        mean_bc = float(
            train_corrected[
                f"{col}_bc"
            ].mean()
        )

        corrected_means[col] = mean_bc

        print(
            f"{col:20s}: "
            f"{mean_bc:.12f}"
        )

    # --------------------------------------------------------
    # Save bias-corrected database
    # --------------------------------------------------------

    corrected.to_csv(
        OUTPUT_CORRECTED,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Complete cases
    # --------------------------------------------------------

    complete = corrected.dropna(
        subset=[
            f"{c}_bc"
            for c in VARIABLES
        ]
    ).copy()

    train = complete[
        complete["period"] == "TRAIN"
    ].copy()

    validation = complete[
        complete["period"] == "VALIDATION"
    ].copy()

    oos = complete[
        complete["period"] == "OOS"
    ].copy()

    print("\n----------------------------------------------")
    print("SPLIT AFTER BIAS CORRECTION")
    print("----------------------------------------------")

    print(
        f"TRAIN      : {len(train):,}"
    )

    print(
        f"VALIDATION : {len(validation):,}"
    )

    print(
        f"OOS        : {len(oos):,}"
    )

    # --------------------------------------------------------
    # Marginal PIT transforms
    # --------------------------------------------------------

    marginals = fit_marginals(
        train
    )

    u_train = to_uniform(
        train,
        marginals
    )

    u_validation = to_uniform(
        validation,
        marginals
    )

    u_oos = to_uniform(
        oos,
        marginals
    )

    # --------------------------------------------------------
    # Gaussian
    # --------------------------------------------------------

    g_corr = gaussian_corr(
        u_train
    )

    g_train_ll = gaussian_ll(
        u_train,
        g_corr
    )

    g_val_ll = gaussian_ll(
        u_validation,
        g_corr
    )

    g_oos_ll = gaussian_ll(
        u_oos,
        g_corr
    )

    k_gauss = D * (D - 1) // 2

    g_val_aic = aic(
        g_val_ll,
        k_gauss
    )

    # --------------------------------------------------------
    # Student-t
    # --------------------------------------------------------

    # Initial dependence matrix
    t_corr = nearest_pd(
        np.corrcoef(
            stats.norm.ppf(u_train),
            rowvar=False
        )
    )

    t_fit = fit_student_t(
        u_train,
        t_corr
    )

    df_t = t_fit["df"]

    t_train_ll = student_t_ll(
        u_train,
        df_t,
        t_corr
    )

    t_val_ll = student_t_ll(
        u_validation,
        df_t,
        t_corr
    )

    t_oos_ll = student_t_ll(
        u_oos,
        df_t,
        t_corr
    )

    k_t = k_gauss + 1

    t_val_aic = aic(
        t_val_ll,
        k_t
    )

    # --------------------------------------------------------
    # Select
    # --------------------------------------------------------

    scores = {
        "Gaussian": g_val_aic,
        "Student_t": t_val_aic,
    }

    selected = min(
        scores,
        key=scores.get
    )

    # --------------------------------------------------------
    # Save correlations
    # --------------------------------------------------------

    pd.DataFrame(
        g_corr,
        index=VARIABLES,
        columns=VARIABLES
    ).to_csv(
        GAUSSIAN_CORR,
        encoding="utf-8-sig"
    )

    pd.DataFrame(
        t_corr,
        index=VARIABLES,
        columns=VARIABLES
    ).to_csv(
        STUDENT_CORR,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Reports
    # --------------------------------------------------------

    bias_report = {
        "gate": "10C.1",
        "method": "TRAIN mean-error bias correction",
        "train_bias": biases,
        "corrected_train_mean": corrected_means,
        "corrected_database": str(
            OUTPUT_CORRECTED
        ),
    }

    with open(
        BIAS_REPORT,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            bias_report,
            f,
            ensure_ascii=False,
            indent=2
        )

    copula_report = {

        "gate": "10C.1",

        "status": "PASS",

        "selected_model":
            selected,

        "train": {
            "rows": int(len(train)),
            "gaussian_loglik": g_train_ll,
            "student_t_loglik": t_train_ll,
        },

        "validation": {
            "rows": int(len(validation)),
            "gaussian_loglik": g_val_ll,
            "student_t_loglik": t_val_ll,
            "gaussian_AIC": g_val_aic,
            "student_t_AIC": t_val_aic,
        },

        "oos_reporting_only": {
            "rows": int(len(oos)),
            "gaussian_loglik": g_oos_ll,
            "student_t_loglik": t_oos_ll,
        },

        "student_t_df": float(
            df_t
        ),

        "correlation_files": {
            "gaussian": str(
                GAUSSIAN_CORR
            ),
            "student_t": str(
                STUDENT_CORR
            ),
        },

        "bias_report": str(
            BIAS_REPORT
        ),

        "corrected_database": str(
            OUTPUT_CORRECTED
        ),
    }

    with open(
        COPULA_REPORT,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            copula_report,
            f,
            ensure_ascii=False,
            indent=2
        )

    # --------------------------------------------------------
    # Console
    # --------------------------------------------------------

    print("\n==============================================")
    print(" COPULA REFIT AFTER BIAS CORRECTION")
    print("==============================================")

    print(
        f"\nGaussian validation AIC : "
        f"{g_val_aic:.6f}"
    )

    print(
        f"Student-t validation AIC: "
        f"{t_val_aic:.6f}"
    )

    print(
        f"\nStudent-t df            : "
        f"{df_t:.6f}"
    )

    print(
        f"Selected model          : "
        f"{selected}"
    )

    print(
        f"\nOOS Gaussian LL         : "
        f"{g_oos_ll:.6f}"
    )

    print(
        f"OOS Student-t LL        : "
        f"{t_oos_ll:.6f}"
    )

    print("\n==============================================")
    print(" GATE 10C.1 COMPLETE")
    print("==============================================")

    print(
        f"\nCorrected database:\n"
        f"{OUTPUT_CORRECTED}"
    )

    print(
        f"\nBias report:\n"
        f"{BIAS_REPORT}"
    )

    print(
        f"\nCopula report:\n"
        f"{COPULA_REPORT}"
    )


if __name__ == "__main__":
    main()
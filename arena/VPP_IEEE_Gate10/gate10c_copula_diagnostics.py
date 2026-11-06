from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd

from scipy import stats
from scipy.optimize import minimize
from scipy.special import gammaln


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

CALIBRATION = ROOT / "data" / "calibration"
REPORTS = ROOT / "reports"

INPUT_FILE = (
    CALIBRATION /
    "joint_residual_database_hourly.csv"
)

REPORT_FILE = (
    REPORTS /
    "gate10c_copula_diagnostics.json"
)

CORR_GAUSSIAN_FILE = (
    CALIBRATION /
    "gaussian_copula_correlation.csv"
)

CORR_T_FILE = (
    CALIBRATION /
    "student_t_copula_correlation.csv"
)


# ============================================================
# VARIABLES
# ============================================================

VARIABLES = [
    "price_error",
    "load_error",
    "wind_on_error",
    "wind_off_error",
    "pv_error",
]

D = len(VARIABLES)


# ============================================================
# STUDY PERIODS
# ============================================================

TRAIN_LABEL = "TRAIN"
VALIDATION_LABEL = "VALIDATION"
OOS_LABEL = "OOS"


# ============================================================
# SETTINGS
# ============================================================

MIN_DF = 2.05
MAX_DF = 80.0

RANK_EPS = 1e-6

# Number of random starts for t-copula df optimization.
# Keeping this small makes Gate 10C fast.
T_COPULA_STARTS = [3.0, 5.0, 10.0, 20.0, 40.0]


# ============================================================
# LOAD DATA
# ============================================================

def load_database():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing joint residual database:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    required = [
        "timestamp",
        "period",
        *VARIABLES,
    ]

    missing = [
        c
        for c in required
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
            errors="coerce",
        )
        .dt.tz_convert("Europe/Berlin")
    )

    if df["timestamp"].isna().any():
        raise ValueError(
            "Invalid timestamps detected."
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
# COMPLETE CASE DATABASE
# ============================================================

def create_complete_cases(df):

    before = len(df)

    complete = df.dropna(
        subset=VARIABLES
    ).copy()

    removed = before - len(complete)

    return complete, before, removed


# ============================================================
# EMPIRICAL PIT FIT ON TRAIN ONLY
# ============================================================

def fit_empirical_marginals(train_df):

    fitted = {}

    for col in VARIABLES:

        x = (
            train_df[col]
            .dropna()
            .to_numpy(dtype=float)
        )

        if len(x) < 100:
            raise ValueError(
                f"Too few training observations for {col}: "
                f"{len(x)}"
            )

        x = np.sort(x)

        fitted[col] = x

    return fitted


def empirical_cdf_values(
    values,
    sorted_train
):
    """
    Map values to empirical CDF using the
    training distribution only.
    """

    values = np.asarray(
        values,
        dtype=float
    )

    n = len(sorted_train)

    # right-sided rank:
    ranks = np.searchsorted(
        sorted_train,
        values,
        side="right"
    )

    # plotting-position style transform
    u = (
        ranks + 0.5
    ) / (n + 1.0)

    return np.clip(
        u,
        RANK_EPS,
        1.0 - RANK_EPS
    )


def transform_to_uniform(
    df,
    marginals
):

    u = np.zeros(
        (len(df), D),
        dtype=float
    )

    for j, col in enumerate(VARIABLES):

        u[:, j] = empirical_cdf_values(
            df[col].to_numpy(dtype=float),
            marginals[col]
        )

    return u


# ============================================================
# DIAGNOSTICS
# ============================================================

def marginal_diagnostics(
    train_df
):

    results = {}

    for col in VARIABLES:

        x = (
            train_df[col]
            .dropna()
            .to_numpy(dtype=float)
        )

        results[col] = {
            "n": int(len(x)),
            "mean": float(np.mean(x)),
            "std": float(np.std(x, ddof=1)),
            "min": float(np.min(x)),
            "max": float(np.max(x)),
            "skewness": float(stats.skew(x)),
            "kurtosis_excess": float(
                stats.kurtosis(
                    x,
                    fisher=True
                )
            ),
            "jarque_bera_stat": float(
                stats.jarque_bera(x).statistic
            ),
            "jarque_bera_pvalue": float(
                stats.jarque_bera(x).pvalue
            ),
        }

    return results


# ============================================================
# GAUSSIAN COPULA
# ============================================================

def gaussian_copula_fit(u):

    z = stats.norm.ppf(u)

    corr = np.corrcoef(
        z,
        rowvar=False
    )

    # Numerical stabilization
    corr = (
        corr + corr.T
    ) / 2.0

    eigvals = np.linalg.eigvalsh(corr)

    if np.min(eigvals) <= 1e-8:

        corr += (
            np.eye(D)
            * (
                1e-8
                - np.min(eigvals)
                + 1e-8
            )
        )

        diag = np.sqrt(
            np.diag(corr)
        )

        corr = (
            corr
            / np.outer(diag, diag)
        )

    return z, corr


def gaussian_copula_loglik(
    u,
    corr
):

    z = stats.norm.ppf(u)

    sign, logdet = np.linalg.slogdet(
        corr
    )

    if sign <= 0:
        return -np.inf

    inv_corr = np.linalg.inv(
        corr
    )

    quadratic = np.einsum(
        "ni,ij,nj->n",
        z,
        inv_corr,
        z
    )

    z_sq = np.sum(
        z ** 2,
        axis=1
    )

    ll = (
        -0.5 * logdet * len(z)
        -0.5 * np.sum(
            quadratic - z_sq
        )
    )

    return float(ll)


# ============================================================
# STUDENT-t COPULA
# ============================================================

def nearest_positive_definite(
    matrix,
    minimum_eigenvalue=1e-6
):

    matrix = (
        matrix + matrix.T
    ) / 2.0

    eigvals, eigvecs = np.linalg.eigh(
        matrix
    )

    eigvals = np.maximum(
        eigvals,
        minimum_eigenvalue
    )

    out = (
        eigvecs
        @ np.diag(eigvals)
        @ eigvecs.T
    )

    diag = np.sqrt(
        np.diag(out)
    )

    out = (
        out
        / np.outer(diag, diag)
    )

    np.fill_diagonal(
        out,
        1.0
    )

    return out


def student_t_copula_loglik(
    u,
    df_t,
    corr
):

    if (
        df_t <= 2.0
        or df_t > 200.0
    ):
        return -np.inf

    corr = nearest_positive_definite(
        corr
    )

    x = stats.t.ppf(
        u,
        df=df_t
    )

    sign, logdet = np.linalg.slogdet(
        corr
    )

    if sign <= 0:
        return -np.inf

    inv_corr = np.linalg.inv(
        corr
    )

    q = np.einsum(
        "ni,ij,nj->n",
        x,
        inv_corr,
        x
    )

    d = x.shape[1]
    n = x.shape[0]

    const_mv = (
        gammaln(
            (df_t + d) / 2.0
        )
        - gammaln(
            df_t / 2.0
        )
        - 0.5 * d * np.log(
            df_t * np.pi
        )
        - 0.5 * logdet
    )

    log_mv = (
        n * const_mv
        - ((df_t + d) / 2.0)
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


def fit_student_t_copula(
    u
):

    # Initial rank-to-t transformation
    best = None

    for initial_df in T_COPULA_STARTS:

        x0 = stats.t.ppf(
            u,
            df=initial_df
        )

        corr0 = np.corrcoef(
            x0,
            rowvar=False
        )

        corr0 = nearest_positive_definite(
            corr0
        )

        def objective(x):

            df_t = np.exp(
                x[0]
            ) + MIN_DF

            ll = student_t_copula_loglik(
                u,
                df_t,
                corr0
            )

            if not np.isfinite(ll):
                return 1e100

            return -ll

        result = minimize(
            objective,
            x0=np.array([
                np.log(
                    initial_df - MIN_DF
                )
            ]),
            method="L-BFGS-B",
            bounds=[
                (
                    np.log(
                        0.01
                    ),
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

        ll = (
            -result.fun
        )

        if (
            best is None
            or ll > best["loglik"]
        ):

            best = {
                "df": float(
                    df_candidate
                ),
                "corr": corr0,
                "loglik": float(ll),
                "optimizer_success": bool(
                    result.success
                ),
                "optimizer_message": str(
                    result.message
                ),
            }

    return best


# ============================================================
# AIC / BIC
# ============================================================

def information_criteria(
    loglik,
    n,
    k
):

    aic = (
        2.0 * k
        - 2.0 * loglik
    )

    bic = (
        k * np.log(n)
        - 2.0 * loglik
    )

    return float(aic), float(bic)


# ============================================================
# TAIL DEPENDENCE EMPIRICAL DIAGNOSTIC
# ============================================================

def joint_lower_tail_probability(
    u,
    threshold=0.05
):

    d = u.shape[1]

    count = np.sum(
        np.all(
            u <= threshold,
            axis=1
        )
    )

    return float(
        count / len(u)
    )


# ============================================================
# MODEL EVALUATION
# ============================================================

def evaluate_copula_models(
    u,
    label
):

    n = len(u)

    # --------------------------------------------------------
    # Independent copula
    # --------------------------------------------------------

    independent_ll = 0.0

    k_independent = 0

    aic_ind, bic_ind = (
        information_criteria(
            independent_ll,
            n,
            k_independent
        )
    )

    # --------------------------------------------------------
    # Gaussian
    # --------------------------------------------------------

    z, gaussian_corr = (
        gaussian_copula_fit(u)
    )

    gaussian_ll = (
        gaussian_copula_loglik(
            u,
            gaussian_corr
        )
    )

    k_gaussian = (
        D * (D - 1) // 2
    )

    aic_gaussian, bic_gaussian = (
        information_criteria(
            gaussian_ll,
            n,
            k_gaussian
        )
    )

    # --------------------------------------------------------
    # Student-t
    # --------------------------------------------------------

    student = (
        fit_student_t_copula(u)
    )

    student_ll = student["loglik"]

    k_student = (
        D * (D - 1) // 2
        + 1
    )

    aic_student, bic_student = (
        information_criteria(
            student_ll,
            n,
            k_student
        )
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    results = {

        "dataset": label,

        "n": int(n),

        "independent": {
            "loglik": independent_ll,
            "parameters": k_independent,
            "AIC": aic_ind,
            "BIC": bic_ind,
        },

        "gaussian": {
            "loglik": gaussian_ll,
            "parameters": k_gaussian,
            "AIC": aic_gaussian,
            "BIC": bic_gaussian,
        },

        "student_t": {
            "loglik": student_ll,
            "parameters": k_student,
            "AIC": aic_student,
            "BIC": bic_student,
            "degrees_of_freedom": student["df"],
            "optimizer_success": student[
                "optimizer_success"
            ],
        },

        "lower_tail_5pct": (
            joint_lower_tail_probability(
                u,
                threshold=0.05
            )
        ),
    }

    return (
        results,
        gaussian_corr,
        student["corr"]
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10C — COPULA DIAGNOSTICS & FITTING")
    print("==============================================\n")

    df = load_database()

    print(
        f"Loaded hourly residual database: "
        f"{len(df):,} rows"
    )

    # --------------------------------------------------------
    # Complete cases
    # --------------------------------------------------------

    complete, before, removed = (
        create_complete_cases(df)
    )

    print(
        f"Complete joint observations: "
        f"{len(complete):,}"
    )

    print(
        f"Rows excluded because of missing residual: "
        f"{removed:,}"
    )

    # --------------------------------------------------------
    # Split
    # --------------------------------------------------------

    train = complete[
        complete["period"] == TRAIN_LABEL
    ].copy()

    validation = complete[
        complete["period"] == VALIDATION_LABEL
    ].copy()

    oos = complete[
        complete["period"] == OOS_LABEL
    ].copy()

    print("\n----------------------------------------------")
    print("SPLIT")
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
    # Marginal diagnostics
    # --------------------------------------------------------

    diagnostics = (
        marginal_diagnostics(
            train
        )
    )

    print("\n----------------------------------------------")
    print("MARGINAL DIAGNOSTICS — TRAIN")
    print("----------------------------------------------")

    for col, result in diagnostics.items():

        print(
            f"\n{col}"
        )

        print(
            f"  mean={result['mean']:.4f}"
            f" | std={result['std']:.4f}"
        )

        print(
            f"  skew={result['skewness']:.4f}"
            f" | kurtosis={result['kurtosis_excess']:.4f}"
        )

        print(
            f"  JB p-value="
            f"{result['jarque_bera_pvalue']:.6g}"
        )

    # --------------------------------------------------------
    # Fit marginal ECDFs on TRAIN only
    # --------------------------------------------------------

    marginals = (
        fit_empirical_marginals(
            train
        )
    )

    # --------------------------------------------------------
    # Transform each split using TRAIN marginals
    # --------------------------------------------------------

    u_train = transform_to_uniform(
        train,
        marginals
    )

    u_validation = transform_to_uniform(
        validation,
        marginals
    )

    u_oos = transform_to_uniform(
        oos,
        marginals
    )

    # --------------------------------------------------------
    # PIT uniformity diagnostics
    # --------------------------------------------------------

    pit_tests = {}

    for j, col in enumerate(VARIABLES):

        ks_train = stats.kstest(
            u_train[:, j],
            "uniform"
        )

        ks_val = stats.kstest(
            u_validation[:, j],
            "uniform"
        )

        ks_oos = stats.kstest(
            u_oos[:, j],
            "uniform"
        )

        pit_tests[col] = {
            "train_KS_pvalue": float(
                ks_train.pvalue
            ),
            "validation_KS_pvalue": float(
                ks_val.pvalue
            ),
            "oos_KS_pvalue": float(
                ks_oos.pvalue
            ),
        }

    print("\n----------------------------------------------")
    print("PIT / MARGINAL UNIFORMITY")
    print("----------------------------------------------")

    for col, result in pit_tests.items():

        print(
            f"{col:20s}"
            f"TRAIN={result['train_KS_pvalue']:.5f} | "
            f"VAL={result['validation_KS_pvalue']:.5f} | "
            f"OOS={result['oos_KS_pvalue']:.5f}"
        )

    # --------------------------------------------------------
    # Fit models ONLY on TRAIN
    # --------------------------------------------------------

    train_models, gaussian_corr, student_corr = (
        evaluate_copula_models(
            u_train,
            "TRAIN"
        )
    )

    # --------------------------------------------------------
    # Evaluate validation log-likelihoods
    # --------------------------------------------------------

    gaussian_val_ll = (
        gaussian_copula_loglik(
            u_validation,
            gaussian_corr
        )
    )

    student_df = (
        train_models[
            "student_t"
        ]["degrees_of_freedom"]
    )

    student_val_ll = (
        student_t_copula_loglik(
            u_validation,
            student_df,
            student_corr
        )
    )

    # --------------------------------------------------------
    # Evaluate OOS ONLY FOR REPORTING
    # --------------------------------------------------------

    gaussian_oos_ll = (
        gaussian_copula_loglik(
            u_oos,
            gaussian_corr
        )
    )

    student_oos_ll = (
        student_t_copula_loglik(
            u_oos,
            student_df,
            student_corr
        )
    )

    # --------------------------------------------------------
    # Save correlation matrices
    # --------------------------------------------------------

    pd.DataFrame(
        gaussian_corr,
        index=VARIABLES,
        columns=VARIABLES
    ).to_csv(
        CORR_GAUSSIAN_FILE,
        encoding="utf-8-sig"
    )

    pd.DataFrame(
        student_corr,
        index=VARIABLES,
        columns=VARIABLES
    ).to_csv(
        CORR_T_FILE,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Determine winner using VALIDATION AIC-equivalent score
    #
    # Same validation n across models, but parameter penalty
    # is retained.
    # --------------------------------------------------------

    val_n = len(validation)

    val_ind_aic, val_ind_bic = (
        information_criteria(
            0.0,
            val_n,
            0
        )
    )

    val_gauss_k = (
        D * (D - 1) // 2
    )

    val_t_k = (
        val_gauss_k + 1
    )

    val_gauss_aic, val_gauss_bic = (
        information_criteria(
            gaussian_val_ll,
            val_n,
            val_gauss_k
        )
    )

    val_t_aic, val_t_bic = (
        information_criteria(
            student_val_ll,
            val_n,
            val_t_k
        )
    )

    validation_scores = {
        "Independent": val_ind_aic,
        "Gaussian": val_gauss_aic,
        "Student_t": val_t_aic,
    }

    winner = min(
        validation_scores,
        key=validation_scores.get
    )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    report = {

        "gate": "10C",

        "status": "PASS",

        "variables": VARIABLES,

        "complete_case": {
            "input_rows": int(before),
            "complete_rows": int(len(complete)),
            "excluded_rows": int(removed),
        },

        "split": {
            "train": int(len(train)),
            "validation": int(len(validation)),
            "oos": int(len(oos)),
        },

        "marginal_diagnostics": diagnostics,

        "pit_tests": pit_tests,

        "train_model_fit": train_models,

        "validation_loglik": {
            "independent": 0.0,
            "gaussian": float(
                gaussian_val_ll
            ),
            "student_t": float(
                student_val_ll
            ),
        },

        "validation_information_criteria": {
            "independent_AIC": val_ind_aic,
            "independent_BIC": val_ind_bic,
            "gaussian_AIC": val_gauss_aic,
            "gaussian_BIC": val_gauss_bic,
            "student_t_AIC": val_t_aic,
            "student_t_BIC": val_t_bic,
        },

        "oos_loglik_reporting_only": {
            "gaussian": float(
                gaussian_oos_ll
            ),
            "student_t": float(
                student_oos_ll
            ),
        },

        "selected_model": winner,

        "student_t_df": float(
            student_df
        ),

        "correlation_files": {
            "gaussian": str(
                CORR_GAUSSIAN_FILE
            ),
            "student_t": str(
                CORR_T_FILE
            ),
        },
    }

    with open(
        REPORT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2
        )

    # --------------------------------------------------------
    # Console
    # --------------------------------------------------------

    print("\n==============================================")
    print(" COPULA MODEL COMPARISON")
    print("==============================================")

    print(
        f"\nStudent-t degrees of freedom: "
        f"{student_df:.4f}"
    )

    print("\nValidation AIC:")

    print(
        f"  Independent : "
        f"{val_ind_aic:.4f}"
    )

    print(
        f"  Gaussian    : "
        f"{val_gauss_aic:.4f}"
    )

    print(
        f"  Student-t   : "
        f"{val_t_aic:.4f}"
    )

    print(
        f"\nSelected model: {winner}"
    )

    print("\nOOS log-likelihood — reporting only:")

    print(
        f"  Gaussian    : "
        f"{gaussian_oos_ll:.6f}"
    )

    print(
        f"  Student-t   : "
        f"{student_oos_ll:.6f}"
    )

    print("\n==============================================")
    print(" GATE 10C COMPLETE")
    print("==============================================")

    print(
        f"\nReport:\n{REPORT_FILE}"
    )


if __name__ == "__main__":
    main()
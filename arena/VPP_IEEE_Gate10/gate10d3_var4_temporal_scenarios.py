from pathlib import Path
import json

import numpy as np
import pandas as pd
from scipy import stats


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

CAL = ROOT / "data" / "calibration"
SCEN = ROOT / "data" / "scenarios"
REPORTS = ROOT / "reports"

CAL.mkdir(parents=True, exist_ok=True)
SCEN.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


INPUT_FILE = (
    CAL /
    "joint_residual_database_hourly_bias_corrected.csv"
)

OUTPUT_FILE = (
    SCEN /
    "temporal_coherent_5000_scenarios_VAR4.csv.gz"
)

SUMMARY_FILE = (
    SCEN /
    "temporal_coherent_VAR4_summary.csv"
)

ACF_FILE = (
    SCEN /
    "temporal_coherent_VAR4_acf_validation.csv"
)

CORR_FILE = (
    SCEN /
    "temporal_coherent_VAR4_correlation.csv"
)

REPORT_FILE = (
    REPORTS /
    "gate10d3_var4_report.json"
)


# ============================================================
# VARIABLES
# ============================================================

VARIABLES = [
    "price_error_bc",
    "load_error_bc",
    "wind_on_error_bc",
    "wind_off_error_bc",
    "pv_error_bc",
]

D = len(VARIABLES)

N_SCENARIOS = 5000
HOURS = 24
VAR_ORDER = 4

STUDENT_DF = 18.546390
SEED = 20260817

RIDGE = 1e-6


# ============================================================
# LOAD TRAIN
# ============================================================

def load_train():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(INPUT_FILE)

    df = pd.read_csv(INPUT_FILE)

    required = [
        "timestamp",
        "period",
        *VARIABLES,
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

    df = df[
        df["period"] == "TRAIN"
    ].dropna(
        subset=VARIABLES
    ).copy()

    df = (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# EMPIRICAL MARGINAL → t LATENT
# ============================================================

def fit_marginals(df):

    marginal = {}

    for col in VARIABLES:

        marginal[col] = np.sort(
            df[col]
            .to_numpy(float)
        )

    return marginal


def to_uniform(
    values,
    sorted_values
):

    ranks = np.searchsorted(
        sorted_values,
        values,
        side="right"
    )

    n = len(sorted_values)

    u = (
        ranks + 0.5
    ) / (n + 1.0)

    return np.clip(
        u,
        1e-6,
        1.0 - 1e-6
    )


def to_latent(
    df,
    marginals
):

    U = np.zeros(
        (len(df), D)
    )

    for j, col in enumerate(VARIABLES):

        U[:, j] = to_uniform(
            df[col].to_numpy(float),
            marginals[col]
        )

    return stats.t.ppf(
        U,
        df=STUDENT_DF
    )


# ============================================================
# FIT VAR(P)
# ============================================================

def fit_var_p(
    X,
    p
):

    n = len(X)

    if n <= p + 10:
        raise ValueError(
            "Too few observations for VAR."
        )

    Y = X[p:]

    blocks = [
        np.ones(
            (len(Y), 1)
        )
    ]

    for lag in range(1, p + 1):

        blocks.append(
            X[
                p - lag:
                n - lag
            ]
        )

    X_design = np.hstack(
        blocks
    )

    # OLS with tiny ridge for stability.
    XtX = (
        X_design.T @ X_design
    )

    ridge = (
        RIDGE *
        np.eye(
            XtX.shape[0]
        )
    )

    beta = np.linalg.solve(
        XtX + ridge,
        X_design.T @ Y
    )

    intercept = beta[0]

    matrices = []

    start = 1

    for lag in range(1, p + 1):

        A = beta[
            start:start + D
        ].T

        matrices.append(A)

        start += D

    fitted = np.tile(
        intercept,
        (len(Y), 1)
    )

    for lag in range(1, p + 1):

        fitted += (
            X[
                p - lag:
                n - lag
            ]
            @ matrices[lag - 1].T
        )

    innovations = Y - fitted

    covariance = np.cov(
        innovations,
        rowvar=False
    )

    covariance += (
        RIDGE *
        np.eye(D)
    )

    return (
        intercept,
        matrices,
        innovations,
        covariance
    )


# ============================================================
# COMPANION MATRIX / STATIONARITY
# ============================================================

def companion_matrix(
    matrices
):

    p = len(matrices)

    top = np.hstack(
        matrices
    )

    if p == 1:
        return top

    bottom = np.zeros(
        (
            D * (p - 1),
            D * p
        )
    )

    bottom[
        :,
        :-D
    ] = np.eye(
        D * (p - 1)
    )

    return np.vstack(
        [
            top,
            bottom
        ]
    )


def spectral_radius(
    matrices
):

    C = companion_matrix(
        matrices
    )

    eig = np.linalg.eigvals(C)

    return float(
        np.max(
            np.abs(eig)
        )
    )


# ============================================================
# GENERATE
# ============================================================

def generate_scenarios(
    X,
    intercept,
    matrices,
    innovations,
    marginal,
    rng
):

    scenarios = []

    innovation_n = len(
        innovations
    )

    # Random historical starting positions
    starts = rng.integers(
        low=VAR_ORDER,
        high=len(X),
        size=N_SCENARIOS
    )

    for scenario_id in range(
        1,
        N_SCENARIOS + 1
    ):

        history = [
            X[
                starts[
                    scenario_id - 1
                ]
                - lag
            ].copy()
            for lag in range(
                VAR_ORDER,
                0,
                -1
            )
        ]

        for hour in range(
            HOURS
        ):

            # VAR(p)
            latent = intercept.copy()

            for lag in range(
                1,
                VAR_ORDER + 1
            ):

                latent += (
                    matrices[
                        lag - 1
                    ]
                    @ history[-lag]
                )

            # Historical innovation bootstrap
            eps = innovations[
                rng.integers(
                    innovation_n
                )
            ]

            latent += eps

            # Update history
            history.append(
                latent.copy()
            )

            history = history[
                -VAR_ORDER:
            ]

            # t latent → U
            u = stats.t.cdf(
                latent,
                df=STUDENT_DF
            )

            u = np.clip(
                u,
                1e-6,
                1 - 1e-6
            )

            row = {
                "scenario_id": scenario_id,
                "hour": hour,
                "probability":
                    1.0 / N_SCENARIOS
            }

            # U → residual
            for j, col in enumerate(
                VARIABLES
            ):

                row[col] = float(
                    np.interp(
                        u[j],
                        np.linspace(
                            0,
                            1,
                            len(marginal[col])
                        ),
                        marginal[col]
                    )
                )

            scenarios.append(
                row
            )

        if scenario_id % 500 == 0:

            print(
                f"[OK] Generated "
                f"{scenario_id:,}/"
                f"{N_SCENARIOS:,}"
            )

    return pd.DataFrame(
        scenarios
    )


# ============================================================
# ACF
# ============================================================

def acf(
    values,
    lag
):

    x = np.asarray(
        values,
        float
    )

    if len(x) <= lag:
        return np.nan

    a = x[:-lag]
    b = x[lag:]

    if (
        np.std(a) == 0
        or
        np.std(b) == 0
    ):
        return np.nan

    return float(
        np.corrcoef(
            a,
            b
        )[0, 1]
    )


def historical_acf(
    train,
    col,
    lag
):

    return acf(
        train[col].to_numpy(),
        lag
    )


def scenario_acf(
    scenarios,
    col,
    lag
):

    values = []

    for _, g in scenarios.groupby(
        "scenario_id"
    ):

        g = g.sort_values(
            "hour"
        )

        value = acf(
            g[col].to_numpy(),
            lag
        )

        if not np.isnan(value):
            values.append(value)

    return float(
        np.mean(values)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10D.3B — VAR(4) TEMPORAL SCENARIOS")
    print("==============================================\n")

    rng = np.random.default_rng(
        SEED
    )

    train = load_train()

    print(
        f"TRAIN rows: "
        f"{len(train):,}"
    )

    # --------------------------------------------------------
    # Marginal transformation
    # --------------------------------------------------------

    marginals = fit_marginals(
        train
    )

    latent = to_latent(
        train,
        marginals
    )

    print(
        f"Latent shape: "
        f"{latent.shape}"
    )

    # --------------------------------------------------------
    # VAR(4)
    # --------------------------------------------------------

    (
        intercept,
        matrices,
        innovations,
        covariance
    ) = fit_var_p(
        latent,
        VAR_ORDER
    )

    radius = spectral_radius(
        matrices
    )

    print("\n----------------------------------------------")
    print("VAR(4) MODEL")
    print("----------------------------------------------")

    print(
        f"Spectral radius: "
        f"{radius:.6f}"
    )

    if radius >= 1:

        raise RuntimeError(
            "VAR(4) is not stationary: "
            f"spectral radius = {radius:.6f}"
        )

    # --------------------------------------------------------
    # Generate
    # --------------------------------------------------------

    scenarios = generate_scenarios(
        latent,
        intercept,
        matrices,
        innovations,
        marginals,
        rng
    )

    expected = (
        N_SCENARIOS
        * HOURS
    )

    if len(scenarios) != expected:
        raise RuntimeError(
            f"Expected {expected:,} rows, "
            f"got {len(scenarios):,}"
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = []

    for col in VARIABLES:

        s = scenarios[col]

        summary.append({
            "variable": col,
            "mean": float(s.mean()),
            "std": float(s.std()),
            "p01": float(s.quantile(.01)),
            "p05": float(s.quantile(.05)),
            "p50": float(s.quantile(.50)),
            "p95": float(s.quantile(.95)),
            "p99": float(s.quantile(.99)),
        })

    summary_df = pd.DataFrame(
        summary
    )

    summary_df.to_csv(
        SUMMARY_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Correlation
    # --------------------------------------------------------

    scenario_corr = (
        scenarios[
            VARIABLES
        ]
        .corr()
    )

    scenario_corr.to_csv(
        CORR_FILE,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # ACF
    # --------------------------------------------------------

    rows = []

    for lag in [
        1,
        2,
        4
    ]:

        for col in VARIABLES:

            h = historical_acf(
                train,
                col,
                lag
            )

            s = scenario_acf(
                scenarios,
                col,
                lag
            )

            rows.append({
                "lag_hours": lag,
                "variable": col,
                "historical_acf": h,
                "scenario_acf": s,
                "absolute_error":
                    abs(s - h)
            })

    acf_df = pd.DataFrame(
        rows
    )

    acf_df.to_csv(
        ACF_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    max_acf_error = float(
        acf_df[
            "absolute_error"
        ].max()
    )

    probability_sum = float(
        scenarios[
            [
                "scenario_id",
                "probability"
            ]
        ]
        .drop_duplicates(
            "scenario_id"
        )[
            "probability"
        ]
        .sum()
    )

    # --------------------------------------------------------
    # Save scenarios
    # --------------------------------------------------------

    scenarios.to_csv(
        OUTPUT_FILE,
        index=False,
        compression="gzip",
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    report = {
        "gate": "10D.3B",
        "status": "PASS",
        "method":
            "Student-t latent-space VAR(4) "
            "with bootstrap innovations",
        "n_scenarios": N_SCENARIOS,
        "hours_per_scenario": HOURS,
        "rows": int(len(scenarios)),
        "student_t_df": STUDENT_DF,
        "var_order": VAR_ORDER,
        "spectral_radius": radius,
        "probability_sum": probability_sum,
        "maximum_acf_error": max_acf_error,
        "outputs": {
            "scenarios":
                str(OUTPUT_FILE),
            "summary":
                str(SUMMARY_FILE),
            "correlation":
                str(CORR_FILE),
            "acf":
                str(ACF_FILE)
        }
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

    print("\n----------------------------------------------")
    print("TEMPORAL VALIDATION — VAR(4)")
    print("----------------------------------------------")

    print(
        acf_df.to_string(
            index=False
        )
    )

    print(
        f"\nMaximum ACF error: "
        f"{max_acf_error:.6f}"
    )

    print(
        f"Probability sum: "
        f"{probability_sum:.12f}"
    )

    print("\n==============================================")
    print(" GATE 10D.3B COMPLETE")
    print("==============================================")

    print(
        f"\nScenario file:\n"
        f"{OUTPUT_FILE}"
    )

    print(
        f"\nACF report:\n"
        f"{ACF_FILE}"
    )

    print(
        f"\nReport:\n"
        f"{REPORT_FILE}"
    )


if __name__ == "__main__":
    main()
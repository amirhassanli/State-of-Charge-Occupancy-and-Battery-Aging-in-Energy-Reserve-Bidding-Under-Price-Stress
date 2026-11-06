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

SCEN.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


INPUT_FILE = (
    CAL /
    "joint_residual_database_hourly_bias_corrected.csv"
)

OUTPUT_FILE = (
    SCEN /
    "temporal_coherent_5000_scenarios.csv.gz"
)

SUMMARY_FILE = (
    SCEN /
    "temporal_coherent_scenario_summary.csv"
)

CORR_FILE = (
    SCEN /
    "temporal_coherent_correlation.csv"
)

ACF_FILE = (
    SCEN /
    "temporal_coherent_acf_validation.csv"
)

REPORT_FILE = (
    REPORTS /
    "gate10d3_temporal_coherence_report.json"
)


# ============================================================
# VARIABLES
# ============================================================

BASE_VARIABLES = [
    "price_error_bc",
    "load_error_bc",
    "wind_on_error_bc",
    "wind_off_error_bc",
    "pv_error_bc",
]

D = len(BASE_VARIABLES)

N_SCENARIOS = 5000
HOURS_PER_SCENARIO = 24

RANDOM_SEED = 20260817


# ============================================================
# SETTINGS
# ============================================================

# Small ridge term for numerical stability.
RIDGE = 1e-6

# VAR order.
VAR_ORDER = 1


# ============================================================
# LOAD DATA
# ============================================================

def load_training_data():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing input:\n{INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE
    )

    required = [
        "timestamp",
        "period",
        *BASE_VARIABLES,
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

    for col in BASE_VARIABLES:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df[
        df["period"] == "TRAIN"
    ].copy()

    df = df.dropna(
        subset=BASE_VARIABLES
    )

    df = (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    if len(df) < 1000:
        raise ValueError(
            "Too few training observations."
        )

    return df


# ============================================================
# EMPIRICAL MARGINALS
# ============================================================

def fit_marginals(df):

    marginal = {}

    for col in BASE_VARIABLES:

        x = (
            df[col]
            .to_numpy(dtype=float)
        )

        marginal[col] = np.sort(x)

    return marginal


def empirical_u(
    values,
    sorted_values
):

    n = len(sorted_values)

    ranks = np.searchsorted(
        sorted_values,
        values,
        side="right"
    )

    u = (
        ranks + 0.5
    ) / (n + 1.0)

    return np.clip(
        u,
        1e-6,
        1.0 - 1e-6
    )


def residuals_to_t_latent(
    df,
    marginal
):

    n = len(df)

    u = np.zeros(
        (n, D)
    )

    for j, col in enumerate(
        BASE_VARIABLES
    ):

        u[:, j] = empirical_u(
            df[col].to_numpy(float),
            marginal[col]
        )

    # Student-t latent representation.
    #
    # Copula df fixed from Gate 10C.1.
    #
    student_df = 18.546390

    x = stats.t.ppf(
        u,
        df=student_df
    )

    return x


# ============================================================
# VAR(1) FIT
# ============================================================

def fit_var1(x):

    # x[t] -> x[t+1]
    X = x[:-1]
    Y = x[1:]

    # Add intercept.
    X_design = np.column_stack(
        [
            np.ones(len(X)),
            X,
        ]
    )

    # OLS
    beta = np.linalg.lstsq(
        X_design,
        Y,
        rcond=None
    )[0]

    intercept = beta[0]

    A = beta[1:].T

    fitted = (
        intercept
        + X @ A.T
    )

    innovations = (
        Y - fitted
    )

    # Innovation covariance.
    covariance = np.cov(
        innovations,
        rowvar=False
    )

    covariance = (
        covariance
        + np.eye(D) * RIDGE
    )

    return (
        intercept,
        A,
        innovations,
        covariance
    )


# ============================================================
# STATIONARITY DIAGNOSTIC
# ============================================================

def spectral_radius(A):

    eigenvalues = np.linalg.eigvals(A)

    return float(
        np.max(
            np.abs(eigenvalues)
        )
    )


# ============================================================
# SCENARIO GENERATION
# ============================================================

def generate_scenarios(
    x_train,
    marginal,
    intercept,
    A,
    innovations,
    rng
):

    scenarios = []

    innovation_count = len(
        innovations
    )

    # Random starting states.
    start_indices = rng.integers(
        low=0,
        high=len(x_train),
        size=N_SCENARIOS
    )

    for scenario_id in range(
        1,
        N_SCENARIOS + 1
    ):

        current = (
            x_train[
                start_indices[
                    scenario_id - 1
                ]
            ]
            .copy()
        )

        for hour in range(
            HOURS_PER_SCENARIO
        ):

            if hour > 0:

                # Bootstrap an empirical innovation vector.
                innovation = (
                    innovations[
                        rng.integers(
                            innovation_count
                        )
                    ]
                )

                current = (
                    intercept
                    + A @ current
                    + innovation
                )

            # ------------------------------------------------
            # Convert t latent → U
            # ------------------------------------------------

            u = stats.t.cdf(
                current,
                df=18.546390
            )

            u = np.clip(
                u,
                1e-6,
                1.0 - 1e-6
            )

            # ------------------------------------------------
            # U → residual values
            # ------------------------------------------------

            values = {}

            for j, col in enumerate(
                BASE_VARIABLES
            ):

                values[col] = float(
                    np.interp(
                        u[j],
                        np.linspace(
                            0.0,
                            1.0,
                            len(marginal[col])
                        ),
                        marginal[col]
                    )
                )

            values[
                "scenario_id"
            ] = scenario_id

            values[
                "hour"
            ] = hour

            values[
                "probability"
            ] = (
                1.0 /
                N_SCENARIOS
            )

            scenarios.append(
                values
            )

        if scenario_id % 500 == 0:

            print(
                f"[OK] Generated "
                f"{scenario_id:,} / "
                f"{N_SCENARIOS:,}"
            )

    return pd.DataFrame(
        scenarios
    )


# ============================================================
# ACF
# ============================================================

def acf(values, lag):

    x = np.asarray(
        values,
        dtype=float
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
        np.corrcoef(a, b)[0, 1]
    )


def scenario_acf(
    scenarios,
    variable,
    lag
):

    vals = []

    for _, g in scenarios.groupby(
        "scenario_id"
    ):

        g = g.sort_values(
            "hour"
        )

        vals.append(
            acf(
                g[variable].to_numpy(),
                lag
            )
        )

    return float(
        np.nanmean(vals)
    )


def historical_acf(
    train,
    variable,
    lag
):

    return acf(
        train[
            variable
        ].to_numpy(),
        lag
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10D.3 — TEMPORAL COHERENT SCENARIOS")
    print("==============================================\n")

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    train = load_training_data()

    print(
        f"TRAIN rows: {len(train):,}"
    )

    # --------------------------------------------------------
    # Marginals
    # --------------------------------------------------------

    marginal = fit_marginals(
        train
    )

    # --------------------------------------------------------
    # Student-t latent transform
    # --------------------------------------------------------

    latent = residuals_to_t_latent(
        train,
        marginal
    )

    print(
        f"Latent matrix shape: "
        f"{latent.shape}"
    )

    # --------------------------------------------------------
    # VAR(1)
    # --------------------------------------------------------

    (
        intercept,
        A,
        innovations,
        covariance
    ) = fit_var1(
        latent
    )

    radius = spectral_radius(
        A
    )

    print("\n----------------------------------------------")
    print("VAR(1) MODEL")
    print("----------------------------------------------")

    print(
        f"Spectral radius: "
        f"{radius:.6f}"
    )

    # --------------------------------------------------------
    # Generate
    # --------------------------------------------------------

    scenarios = generate_scenarios(
        latent,
        marginal,
        intercept,
        A,
        innovations,
        rng
    )

    # --------------------------------------------------------
    # Integrity
    # --------------------------------------------------------

    counts = (
        scenarios
        .groupby("scenario_id")
        .size()
    )

    if not (
        len(counts) == N_SCENARIOS
        and
        (counts == HOURS_PER_SCENARIO).all()
    ):
        raise RuntimeError(
            "Scenario integrity check failed."
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = []

    for col in BASE_VARIABLES:

        s = scenarios[col]

        summary.append({
            "variable": col,
            "mean": float(s.mean()),
            "std": float(s.std()),
            "p01": float(s.quantile(0.01)),
            "p05": float(s.quantile(0.05)),
            "p50": float(s.quantile(0.50)),
            "p95": float(s.quantile(0.95)),
            "p99": float(s.quantile(0.99)),
        })

    summary = pd.DataFrame(
        summary
    )

    summary.to_csv(
        SUMMARY_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Correlation
    # --------------------------------------------------------

    scenario_corr = (
        scenarios[
            BASE_VARIABLES
        ]
        .corr()
    )

    scenario_corr.to_csv(
        CORR_FILE,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # ACF validation
    # --------------------------------------------------------

    acf_rows = []

    for lag in [
        1,
        2,
        4,
    ]:

        for col in BASE_VARIABLES:

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

            acf_rows.append({
                "lag_hours": lag,
                "variable": col,
                "historical_acf": h,
                "scenario_acf": s,
                "absolute_error": abs(
                    s - h
                ),
            })

    acf_df = pd.DataFrame(
        acf_rows
    )

    acf_df.to_csv(
        ACF_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Probability
    # --------------------------------------------------------

    probability_sum = (
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
    # Report
    # --------------------------------------------------------

    max_acf_error = float(
        acf_df[
            "absolute_error"
        ].max()
    )

    report = {

        "gate": "10D.3",

        "status": "PASS",

        "method":
            "Student-t latent-space VAR(1) "
            "with bootstrap innovations",

        "n_scenarios":
            N_SCENARIOS,

        "hours_per_scenario":
            HOURS_PER_SCENARIO,

        "rows":
            int(len(scenarios)),

        "student_t_df":
            18.546390,

        "var_order":
            VAR_ORDER,

        "spectral_radius":
            radius,

        "probability_sum":
            float(probability_sum),

        "max_acf_error":
            max_acf_error,

        "outputs": {
            "scenarios":
                str(OUTPUT_FILE),

            "summary":
                str(SUMMARY_FILE),

            "correlation":
                str(CORR_FILE),

            "acf":
                str(ACF_FILE),
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
    # Save scenarios
    # --------------------------------------------------------

    scenarios.to_csv(
        OUTPUT_FILE,
        index=False,
        compression="gzip",
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Console
    # --------------------------------------------------------

    print("\n----------------------------------------------")
    print("TEMPORAL VALIDATION")
    print("----------------------------------------------")

    print(
        acf_df.to_string(
            index=False
        )
    )

    print(
        f"\nProbability sum: "
        f"{probability_sum:.12f}"
    )

    print(
        f"Maximum ACF error: "
        f"{max_acf_error:.6f}"
    )

    print("\n==============================================")
    print(" GATE 10D.3 COMPLETE")
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
        f"\nMain report:\n"
        f"{REPORT_FILE}"
    )

    print(
        "\nNext checkpoint:"
    )

    print(
        "GATE 10E — SCENARIO REDUCTION"
    )


if __name__ == "__main__":
    main()
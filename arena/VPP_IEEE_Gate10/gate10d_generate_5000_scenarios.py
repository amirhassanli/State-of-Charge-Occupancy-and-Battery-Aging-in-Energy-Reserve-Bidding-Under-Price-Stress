from pathlib import Path
import json

import numpy as np
import pandas as pd
from scipy import stats


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

CALIBRATION = ROOT / "data" / "calibration"
SCENARIOS = ROOT / "data" / "scenarios"
REPORTS = ROOT / "reports"

SCENARIOS.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


RESIDUAL_FILE = (
    CALIBRATION
    / "joint_residual_database_hourly_bias_corrected.csv"
)

CORR_FILE = (
    CALIBRATION
    / "student_t_copula_correlation_bias_corrected.csv"
)

COPULA_REPORT = (
    REPORTS
    / "gate10c_refit_bias_corrected.json"
)

OUTPUT_FILE = (
    SCENARIOS
    / "raw_5000_joint_hourly_scenarios_bias_corrected.csv.gz"
)

SUMMARY_FILE = (
    SCENARIOS
    / "raw_5000_scenario_summary_bias_corrected.csv"
)

CORR_SCENARIO_FILE = (
    SCENARIOS
    / "raw_5000_scenario_correlation_bias_corrected.csv"
)

REPORT_FILE = (
    REPORTS
    / "gate10d_scenario_generation_bias_corrected.json"
)


# ============================================================
# VARIABLES — IMPORTANT: BIAS-CORRECTED COLUMNS
# ============================================================

BASE_VARIABLES = [
    "price_error",
    "load_error",
    "wind_on_error",
    "wind_off_error",
    "pv_error",
]

BC_VARIABLES = [
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
# LOAD INPUTS
# ============================================================

def load_inputs():

    if not RESIDUAL_FILE.exists():
        raise FileNotFoundError(
            f"Missing residual database:\n{RESIDUAL_FILE}"
        )

    if not CORR_FILE.exists():
        raise FileNotFoundError(
            f"Missing Student-t correlation matrix:\n{CORR_FILE}"
        )

    if not COPULA_REPORT.exists():
        raise FileNotFoundError(
            f"Missing Copula report:\n{COPULA_REPORT}"
        )

    df = pd.read_csv(
        RESIDUAL_FILE
    )

    required = [
        "timestamp",
        "period",
        *BASE_VARIABLES,
        *BC_VARIABLES,
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns in bias-corrected database: {missing}"
        )

    df["timestamp"] = (
        pd.to_datetime(
            df["timestamp"],
            utc=True,
            errors="coerce"
        )
        .dt.tz_convert("Europe/Berlin")
    )

    for col in (
        BASE_VARIABLES + BC_VARIABLES
    ):
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    corr = pd.read_csv(
        CORR_FILE,
        index_col=0
    )

    corr = corr.loc[
        BASE_VARIABLES,
        BASE_VARIABLES
    ].to_numpy(dtype=float)

    with open(
        COPULA_REPORT,
        "r",
        encoding="utf-8"
    ) as f:
        report = json.load(f)

    df_t = float(
        report["student_t_df"]
    )

    return df, corr, df_t


# ============================================================
# NUMERICAL STABILIZATION
# ============================================================

def nearest_positive_definite(matrix):

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


# ============================================================
# EMPIRICAL MARGINALS — TRAIN BIAS-CORRECTED ONLY
# ============================================================

def fit_empirical_marginals(train_df):

    marginals = {}

    for col in BC_VARIABLES:

        x = (
            train_df[col]
            .dropna()
            .to_numpy(dtype=float)
        )

        if len(x) < 100:
            raise ValueError(
                f"Too few TRAIN observations for {col}: {len(x)}"
            )

        marginals[col] = np.sort(x)

    return marginals


def inverse_empirical_cdf(
    u,
    sorted_values
):

    n = len(sorted_values)

    probabilities = np.linspace(
        0.0,
        1.0,
        n
    )

    return np.interp(
        u,
        probabilities,
        sorted_values
    )


# ============================================================
# GENERATE JOINT UNIFORM SAMPLE
# ============================================================

def generate_joint_uniform(
    n,
    df_t,
    correlation,
    rng
):

    latent = stats.multivariate_t.rvs(
        loc=np.zeros(D),
        shape=correlation,
        df=df_t,
        size=n,
        random_state=rng
    )

    latent = np.asarray(
        latent,
        dtype=float
    )

    if latent.ndim == 1:
        latent = latent.reshape(
            1,
            -1
        )

    u = stats.t.cdf(
        latent,
        df=df_t
    )

    return np.clip(
        u,
        1e-8,
        1.0 - 1e-8
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10D.1 — BIAS-CORRECTED 5,000 SCENARIOS")
    print("==============================================\n")

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    df, correlation, df_t = load_inputs()

    print(
        f"Historical rows : {len(df):,}"
    )

    print(
        f"Student-t df    : {df_t:.6f}"
    )

    # --------------------------------------------------------
    # TRAIN ONLY
    # --------------------------------------------------------

    train = df[
        df["period"] == "TRAIN"
    ].copy()

    train = train.dropna(
        subset=BC_VARIABLES
    )

    print(
        f"TRAIN complete rows: {len(train):,}"
    )

    # --------------------------------------------------------
    # IMPORTANT FIX:
    # Marginals are fit ONLY from *_bc columns.
    # --------------------------------------------------------

    marginals = fit_empirical_marginals(
        train
    )

    records = []

    for scenario_id in range(
        1,
        N_SCENARIOS + 1
    ):

        for hour in range(
            HOURS_PER_SCENARIO
        ):

            u = generate_joint_uniform(
                n=1,
                df_t=df_t,
                correlation=correlation,
                rng=rng
            )[0]

            values = []

            for j, bc_col in enumerate(
                BC_VARIABLES
            ):

                value = inverse_empirical_cdf(
                    u[j],
                    marginals[bc_col]
                )

                values.append(
                    float(value)
                )

            records.append({
                "scenario_id": scenario_id,
                "hour": hour,
                "price_error_bc": values[0],
                "load_error_bc": values[1],
                "wind_on_error_bc": values[2],
                "wind_off_error_bc": values[3],
                "pv_error_bc": values[4],
                "probability": 1.0 / N_SCENARIOS,
            })

        if scenario_id % 500 == 0:
            print(
                f"[OK] Generated "
                f"{scenario_id:,} / "
                f"{N_SCENARIOS:,}"
            )

    scenarios = pd.DataFrame(
        records
    )

    expected_rows = (
        N_SCENARIOS
        * HOURS_PER_SCENARIO
    )

    if len(scenarios) != expected_rows:
        raise RuntimeError(
            f"Expected {expected_rows:,} rows; "
            f"got {len(scenarios):,}"
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    summary_rows = []

    for col in BC_VARIABLES:

        s = scenarios[col]

        summary_rows.append({
            "variable": col,
            "mean": float(s.mean()),
            "std": float(s.std()),
            "min": float(s.min()),
            "max": float(s.max()),
            "p01": float(s.quantile(0.01)),
            "p05": float(s.quantile(0.05)),
            "p50": float(s.quantile(0.50)),
            "p95": float(s.quantile(0.95)),
            "p99": float(s.quantile(0.99)),
        })

    summary = pd.DataFrame(
        summary_rows
    )

    # --------------------------------------------------------
    # CORRELATION
    # --------------------------------------------------------

    scenario_corr = (
        scenarios[
            BC_VARIABLES
        ]
        .corr()
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    scenarios.to_csv(
        OUTPUT_FILE,
        index=False,
        compression="gzip",
        encoding="utf-8"
    )

    summary.to_csv(
        SUMMARY_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    scenario_corr.to_csv(
        CORR_SCENARIO_FILE,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # INTEGRITY
    # --------------------------------------------------------

    probability_sum = float(
        scenarios[
            [
                "scenario_id",
                "probability"
            ]
        ]
        .drop_duplicates("scenario_id")
        ["probability"]
        .sum()
    )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    report = {
        "gate": "10D.1",
        "status": "PASS",
        "random_seed": RANDOM_SEED,
        "n_scenarios": N_SCENARIOS,
        "hours_per_scenario": HOURS_PER_SCENARIO,
        "rows": int(len(scenarios)),
        "student_t_df": df_t,
        "marginal_source": "TRAIN bias-corrected residuals",
        "probability_sum": probability_sum,
        "outputs": {
            "scenarios": str(OUTPUT_FILE),
            "summary": str(SUMMARY_FILE),
            "correlation": str(CORR_SCENARIO_FILE),
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
    # CONSOLE
    # --------------------------------------------------------

    print("\n==============================================")
    print(" GATE 10D.1 BIAS-CORRECTED COMPLETE")
    print("==============================================")

    print(
        f"\nScenarios       : {N_SCENARIOS:,}"
    )

    print(
        f"Rows            : {len(scenarios):,}"
    )

    print(
        f"Probability sum : {probability_sum:.12f}"
    )

    print("\nScenario means:")
    print(summary[
        [
            "variable",
            "mean",
            "std"
        ]
    ].to_string(index=False))

    print(
        f"\nScenario file:\n{OUTPUT_FILE}"
    )

    print(
        f"\nReport:\n{REPORT_FILE}"
    )


if __name__ == "__main__":
    main()

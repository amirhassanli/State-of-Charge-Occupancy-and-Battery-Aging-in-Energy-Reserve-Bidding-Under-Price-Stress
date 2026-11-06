from pathlib import Path
import json

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

CALIBRATION = ROOT / "data" / "calibration"
SCENARIOS = ROOT / "data" / "scenarios"
REPORTS = ROOT / "reports"

SCENARIOS.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


INPUT_FILE = (
    CALIBRATION /
    "joint_residual_database_hourly_bias_corrected.csv"
)

OUTPUT_FILE = (
    SCENARIOS /
    "empirical_block_bootstrap_5000_scenarios.csv.gz"
)

SUMMARY_FILE = (
    SCENARIOS /
    "empirical_block_bootstrap_summary.csv"
)

ACF_FILE = (
    SCENARIOS /
    "empirical_block_bootstrap_acf_validation.csv"
)

CORR_FILE = (
    SCENARIOS /
    "empirical_block_bootstrap_correlation.csv"
)

REPORT_FILE = (
    REPORTS /
    "gate10d3c_block_bootstrap_report.json"
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

N_SCENARIOS = 5000
BLOCK_LENGTH = 24
SEED = 20260817


# ============================================================
# LOAD TRAIN
# ============================================================

def load_train():

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
    ].copy()

    df = df.dropna(
        subset=VARIABLES
    )

    df = (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# ACF
# ============================================================

def acf(
    values,
    lag
):

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

    for _, group in scenarios.groupby(
        "scenario_id"
    ):

        group = group.sort_values(
            "hour"
        )

        value = acf(
            group[col].to_numpy(),
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
    print(" GATE 10D.3C — 24-HOUR MOVING BLOCK BOOTSTRAP")
    print("==============================================\n")

    rng = np.random.default_rng(
        SEED
    )

    train = load_train()

    print(
        f"TRAIN rows: {len(train):,}"
    )

    if len(train) < BLOCK_LENGTH:
        raise ValueError(
            "TRAIN data shorter than block length."
        )

    # --------------------------------------------------------
    # Number of valid contiguous blocks
    # --------------------------------------------------------

    max_start = (
        len(train)
        - BLOCK_LENGTH
    )

    print(
        f"Valid block starts: "
        f"{max_start + 1:,}"
    )

    # --------------------------------------------------------
    # Generate scenarios
    # --------------------------------------------------------

    records = []

    for scenario_id in range(
        1,
        N_SCENARIOS + 1
    ):

        start = int(
            rng.integers(
                0,
                max_start + 1
            )
        )

        block = train.iloc[
            start:
            start + BLOCK_LENGTH
        ].copy()

        block = block.reset_index(
            drop=True
        )

        for hour in range(
            BLOCK_LENGTH
        ):

            row = {
                "scenario_id":
                    scenario_id,

                "hour":
                    hour,

                "probability":
                    1.0 / N_SCENARIOS,
            }

            for col in VARIABLES:

                row[col] = float(
                    block.loc[
                        hour,
                        col
                    ]
                )

            records.append(
                row
            )

        if scenario_id % 500 == 0:

            print(
                f"[OK] Generated "
                f"{scenario_id:,}/"
                f"{N_SCENARIOS:,}"
            )

    scenarios = pd.DataFrame(
        records
    )

    expected_rows = (
        N_SCENARIOS
        * BLOCK_LENGTH
    )

    if len(scenarios) != expected_rows:
        raise RuntimeError(
            f"Expected {expected_rows:,} rows, "
            f"got {len(scenarios):,}"
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
        (counts == BLOCK_LENGTH).all()
    ):
        raise RuntimeError(
            "Scenario integrity failed."
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
    # Distribution summary
    # --------------------------------------------------------

    summary_rows = []

    for col in VARIABLES:

        s = scenarios[col]

        summary_rows.append({
            "variable": col,
            "mean": float(
                s.mean()
            ),
            "std": float(
                s.std()
            ),
            "p01": float(
                s.quantile(0.01)
            ),
            "p05": float(
                s.quantile(0.05)
            ),
            "p50": float(
                s.quantile(0.50)
            ),
            "p95": float(
                s.quantile(0.95)
            ),
            "p99": float(
                s.quantile(0.99)
            ),
        })

    summary = pd.DataFrame(
        summary_rows
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

    # --------------------------------------------------------
    # ACF validation
    # --------------------------------------------------------

    acf_rows = []

    for lag in [
        1,
        2,
        4,
    ]:

        for col in VARIABLES:

            hist = historical_acf(
                train,
                col,
                lag
            )

            scen = scenario_acf(
                scenarios,
                col,
                lag
            )

            acf_rows.append({
                "lag_hours":
                    lag,

                "variable":
                    col,

                "historical_acf":
                    hist,

                "scenario_acf":
                    scen,

                "absolute_error":
                    abs(
                        scen - hist
                    ),
            })

    acf_df = pd.DataFrame(
        acf_rows
    )

    max_acf_error = float(
        acf_df[
            "absolute_error"
        ].max()
    )

    mean_acf_error = float(
        acf_df[
            "absolute_error"
        ].mean()
    )

    # --------------------------------------------------------
    # Save
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
        CORR_FILE,
        encoding="utf-8-sig"
    )

    acf_df.to_csv(
        ACF_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    report = {
        "gate":
            "10D.3C",

        "status":
            "PASS",

        "method":
            "Empirical moving block bootstrap",

        "block_length_hours":
            BLOCK_LENGTH,

        "n_scenarios":
            N_SCENARIOS,

        "rows":
            int(len(scenarios)),

        "probability_sum":
            probability_sum,

        "mean_acf_error":
            mean_acf_error,

        "max_acf_error":
            max_acf_error,

        "seed":
            SEED,

        "interpretation":
            "Historical contiguous 24-hour blocks "
            "are resampled with replacement to preserve "
            "temporal and cross-variable dependence.",

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
        f"\nMean ACF error: "
        f"{mean_acf_error:.6f}"
    )

    print(
        f"Maximum ACF error: "
        f"{max_acf_error:.6f}"
    )

    print(
        f"\nProbability sum: "
        f"{probability_sum:.12f}"
    )

    print("\n==============================================")
    print(" GATE 10D.3C COMPLETE")
    print("==============================================")

    print(
        f"\nScenario file:\n"
        f"{OUTPUT_FILE}"
    )

    print(
        f"\nACF validation:\n"
        f"{ACF_FILE}"
    )

    print(
        f"\nReport:\n"
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
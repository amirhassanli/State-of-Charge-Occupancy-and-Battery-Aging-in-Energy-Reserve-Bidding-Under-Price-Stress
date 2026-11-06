from pathlib import Path
import json

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

CAL = ROOT / "data" / "calibration"
SCEN = ROOT / "data" / "scenarios"
REPORTS = ROOT / "reports"

HIST_FILE = (
    CAL /
    "joint_residual_database_hourly_bias_corrected.csv"
)

SCEN_FILE = (
    SCEN /
    "empirical_block_bootstrap_5000_scenarios.csv.gz"
)

REPORT_FILE = (
    REPORTS /
    "gate10d3d_correct_acf_validation.json"
)

OUTPUT_FILE = (
    SCEN /
    "gate10d3d_acf_corrected.csv"
)


VARIABLES = [
    "price_error_bc",
    "load_error_bc",
    "wind_on_error_bc",
    "wind_off_error_bc",
    "pv_error_bc",
]

LAGS = [1, 2, 4]


# ============================================================
# LOAD
# ============================================================

def load_data():

    hist = pd.read_csv(
        HIST_FILE
    )

    scen = pd.read_csv(
        SCEN_FILE
    )

    hist["timestamp"] = (
        pd.to_datetime(
            hist["timestamp"],
            utc=True,
            errors="coerce"
        )
        .dt.tz_convert("Europe/Berlin")
    )

    hist = hist[
        hist["period"] == "TRAIN"
    ].copy()

    for col in VARIABLES:
        hist[col] = pd.to_numeric(
            hist[col],
            errors="coerce"
        )
        scen[col] = pd.to_numeric(
            scen[col],
            errors="coerce"
        )

    scen = (
        scen
        .sort_values(
            ["scenario_id", "hour"]
        )
        .reset_index(drop=True)
    )

    return hist, scen


# ============================================================
# HISTORICAL ACF
# ============================================================

def historical_acf(
    hist,
    col,
    lag
):

    x = (
        hist[col]
        .dropna()
        .to_numpy(float)
    )

    x1 = x[:-lag]
    x2 = x[lag:]

    return float(
        np.corrcoef(
            x1,
            x2
        )[0, 1]
    )


# ============================================================
# POOLED SCENARIO ACF
# ============================================================

def pooled_scenario_acf(
    scen,
    col,
    lag
):

    x1 = []
    x2 = []

    for _, g in scen.groupby(
        "scenario_id"
    ):

        g = (
            g
            .sort_values("hour")
        )

        values = (
            g[col]
            .to_numpy(float)
        )

        if len(values) <= lag:
            continue

        x1.extend(
            values[:-lag]
        )

        x2.extend(
            values[lag:]
        )

    x1 = np.asarray(
        x1,
        dtype=float
    )

    x2 = np.asarray(
        x2,
        dtype=float
    )

    return float(
        np.corrcoef(
            x1,
            x2
        )[0, 1]
    )


# ============================================================
# BLOCK-LOCAL ACF
# ============================================================

def block_local_acf(
    scen,
    col,
    lag
):

    values = []

    for _, g in scen.groupby(
        "scenario_id"
    ):

        g = g.sort_values("hour")

        x = g[col].to_numpy(float)

        if len(x) <= lag:
            continue

        a = x[:-lag]
        b = x[lag:]

        if (
            np.std(a) == 0
            or
            np.std(b) == 0
        ):
            continue

        values.append(
            np.corrcoef(
                a,
                b
            )[0, 1]
        )

    return float(
        np.mean(values)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10D.3D — CORRECT ACF VALIDATION")
    print("==============================================\n")

    hist, scen = load_data()

    rows = []

    for lag in LAGS:

        for col in VARIABLES:

            h = historical_acf(
                hist,
                col,
                lag
            )

            pooled = pooled_scenario_acf(
                scen,
                col,
                lag
            )

            local = block_local_acf(
                scen,
                col,
                lag
            )

            rows.append({
                "lag_hours": lag,
                "variable": col,
                "historical_acf": h,
                "scenario_pooled_acf": pooled,
                "scenario_block_local_acf": local,
                "pooled_absolute_error":
                    abs(pooled - h),
                "local_absolute_error":
                    abs(local - h),
            })

    result = pd.DataFrame(
        rows
    )

    result.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        result.to_string(
            index=False
        )
    )

    pooled_mae = float(
        result[
            "pooled_absolute_error"
        ].mean()
    )

    local_mae = float(
        result[
            "local_absolute_error"
        ].mean()
    )

    pooled_max = float(
        result[
            "pooled_absolute_error"
        ].max()
    )

    report = {
        "gate": "10D.3D",

        "method":
            "Pooled lag-pair ACF validation "
            "without crossing scenario boundaries",

        "pooled_mean_acf_error":
            pooled_mae,

        "pooled_max_acf_error":
            pooled_max,

        "block_local_mean_acf_error":
            local_mae,

        "interpretation":
            "Pooled ACF is the primary validation metric. "
            "Block-local ACF is reported only diagnostically.",
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

    print("\n----------------------------------------------")
    print("SUMMARY")
    print("----------------------------------------------")

    print(
        f"Pooled mean ACF error : "
        f"{pooled_mae:.6f}"
    )

    print(
        f"Pooled max ACF error  : "
        f"{pooled_max:.6f}"
    )

    print(
        f"Local mean ACF error  : "
        f"{local_mae:.6f}"
    )

    print("\n==============================================")
    print(" GATE 10D.3D COMPLETE")
    print("==============================================")

    print(
        f"\nValidation:\n"
        f"{OUTPUT_FILE}"
    )

    print(
        f"\nReport:\n"
        f"{REPORT_FILE}"
    )


if __name__ == "__main__":
    main()
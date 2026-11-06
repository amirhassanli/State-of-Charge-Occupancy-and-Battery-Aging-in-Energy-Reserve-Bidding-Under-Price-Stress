from pathlib import Path
import json

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

PROCESSED = ROOT / "data" / "processed"
CALIBRATION = ROOT / "data" / "calibration"
REPORTS = ROOT / "reports"

PROCESSED.mkdir(parents=True, exist_ok=True)
CALIBRATION.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


PHYSICAL_MASTER = (
    PROCESSED / "master_physical_15min.csv"
)

LOAD_FORECAST_FILE = (
    PROCESSED /
    "load_forecast_derived_from_smard.csv"
)

PRICE_CALIBRATION = (
    CALIBRATION /
    "da_price_calibrated_forecast.csv"
)

WIND_ON_CALIBRATION = (
    CALIBRATION /
    "wind_onshore_calibration.csv"
)

WIND_OFF_CALIBRATION = (
    CALIBRATION /
    "wind_offshore_calibration.csv"
)

PV_CALIBRATION = (
    CALIBRATION /
    "pv_calibration.csv"
)

OUTPUT_15M = (
    CALIBRATION /
    "joint_physical_residuals_15min.csv"
)

OUTPUT_HOURLY = (
    CALIBRATION /
    "joint_residual_database_hourly.csv"
)

CORR_FILE = (
    CALIBRATION /
    "joint_residual_correlation.csv"
)

REPORT_FILE = (
    REPORTS /
    "gate10b5_joint_residual_database.json"
)


# ============================================================
# STUDY PERIODS
# ============================================================

TRAIN_START = pd.Timestamp(
    "2024-01-01",
    tz="Europe/Berlin"
)

TRAIN_END = pd.Timestamp(
    "2024-12-31 23:59:59",
    tz="Europe/Berlin"
)

VAL_START = pd.Timestamp(
    "2025-01-01",
    tz="Europe/Berlin"
)

VAL_END = pd.Timestamp(
    "2025-06-30 23:59:59",
    tz="Europe/Berlin"
)

OOS_START = pd.Timestamp(
    "2025-07-01",
    tz="Europe/Berlin"
)

OOS_END = pd.Timestamp(
    "2025-09-30 23:59:59",
    tz="Europe/Berlin"
)


def assign_period(ts):
    if TRAIN_START <= ts <= TRAIN_END:
        return "TRAIN"

    if VAL_START <= ts <= VAL_END:
        return "VALIDATION"

    if OOS_START <= ts <= OOS_END:
        return "OOS"

    return "OUTSIDE"


# ============================================================
# GENERIC TIMESTAMP NORMALIZATION
# ============================================================

def normalize_timestamp(series):
    """
    Parse timestamps robustly and convert to Europe/Berlin.
    """

    result = pd.to_datetime(
        series,
        utc=True,
        errors="coerce"
    )

    if result.isna().any():
        bad = int(result.isna().sum())
        raise ValueError(
            f"{bad} invalid timestamps detected."
        )

    return result.dt.tz_convert("Europe/Berlin")


# ============================================================
# LOAD STANDARD MASTER
# ============================================================

def load_master(path, required_columns):

    if not path.exists():
        raise FileNotFoundError(
            f"Missing file:\n{path}"
        )

    df = pd.read_csv(path)

    missing = [
        c for c in required_columns
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{path.name}: missing columns: {missing}"
        )

    df["timestamp"] = normalize_timestamp(
        df["timestamp"]
    )

    df = (
        df
        .sort_values("timestamp")
        .drop_duplicates("timestamp")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# LOAD CALIBRATION ERROR FILE
# ============================================================

def load_error_series(
    path,
    output_error_name
):
    """
    Read one calibration CSV and explicitly locate the
    'error' column by name.

    This avoids dependence on column order.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Missing calibration file:\n{path}"
        )

    df = pd.read_csv(path)

    print(
        f"\nReading calibration file: {path.name}"
    )

    print(
        "Columns:",
        list(df.columns)
    )

    if "timestamp" not in df.columns:
        raise ValueError(
            f"{path.name}: timestamp column missing."
        )

    if "error" not in df.columns:
        raise ValueError(
            f"{path.name}: explicit 'error' column "
            f"not found. Available columns: {list(df.columns)}"
        )

    df["timestamp"] = normalize_timestamp(
        df["timestamp"]
    )

    df["error"] = pd.to_numeric(
        df["error"],
        errors="coerce"
    )

    result = df[
        [
            "timestamp",
            "error"
        ]
    ].copy()

    result = result.rename(
        columns={
            "error": output_error_name
        }
    )

    result = (
        result
        .sort_values("timestamp")
        .drop_duplicates("timestamp")
        .reset_index(drop=True)
    )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10B.5 — JOINT RESIDUAL DATABASE")
    print("==============================================\n")

    # --------------------------------------------------------
    # 1. LOAD ACTUAL PHYSICAL DATA
    # --------------------------------------------------------

    physical = load_master(
        PHYSICAL_MASTER,
        [
            "timestamp",
            "load_actual",
            "wind_on_actual",
            "wind_off_actual",
            "pv_actual",
        ]
    )

    print(
        f"Physical master loaded: "
        f"{len(physical):,} rows"
    )

    # --------------------------------------------------------
    # 2. LOAD DERIVED LOAD FORECAST
    # --------------------------------------------------------

    load_fc = load_master(
        LOAD_FORECAST_FILE,
        [
            "timestamp",
            "load_forecast",
        ]
    )

    print(
        f"Load forecast loaded: "
        f"{len(load_fc):,} rows"
    )

    # --------------------------------------------------------
    # 3. LOAD WIND/PV CALIBRATION ERRORS
    # --------------------------------------------------------

    wind_on = load_error_series(
        WIND_ON_CALIBRATION,
        "wind_on_error"
    )

    wind_off = load_error_series(
        WIND_OFF_CALIBRATION,
        "wind_off_error"
    )

    pv = load_error_series(
        PV_CALIBRATION,
        "pv_error"
    )

    # --------------------------------------------------------
    # 4. BUILD LOAD ERROR
    # --------------------------------------------------------

    load = physical[
        [
            "timestamp",
            "load_actual"
        ]
    ].merge(
        load_fc[
            [
                "timestamp",
                "load_forecast"
            ]
        ],
        on="timestamp",
        how="inner",
        validate="one_to_one"
    )

    load["load_error"] = (
        load["load_actual"]
        - load["load_forecast"]
    )

    load = load[
        [
            "timestamp",
            "load_error"
        ]
    ]

    print(
        f"\nLoad residual rows: "
        f"{len(load):,}"
    )

    # --------------------------------------------------------
    # 5. BUILD 15-MIN JOINT PHYSICAL RESIDUAL DATABASE
    # --------------------------------------------------------

    residuals = load.copy()

    for df in [
        wind_on,
        wind_off,
        pv
    ]:

        residuals = residuals.merge(
            df,
            on="timestamp",
            how="inner",
            validate="one_to_one"
        )

    required_residual_columns = [
        "timestamp",
        "load_error",
        "wind_on_error",
        "wind_off_error",
        "pv_error"
    ]

    missing = [
        c for c in required_residual_columns
        if c not in residuals.columns
    ]

    if missing:
        raise ValueError(
            f"Residual database missing columns: {missing}"
        )

    residuals = residuals[
        required_residual_columns
    ].copy()

    residuals["period"] = (
        residuals["timestamp"]
        .apply(assign_period)
    )

    residuals = residuals[
        residuals["period"] != "OUTSIDE"
    ].copy()

    residuals = (
        residuals
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # 6. SAVE 15-MIN DATABASE
    # --------------------------------------------------------

    residuals.to_csv(
        OUTPUT_15M,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"\n[OK] 15-min physical residual database: "
        f"{len(residuals):,} rows"
    )

    # --------------------------------------------------------
    # 7. CONVERT PHYSICAL ERRORS TO HOURLY BLOCKS
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # We aggregate physical forecast errors by hour.
    # We DO NOT floor the timezone-aware timestamps.
    # Resampling on the timestamp index is DST-aware.
    # --------------------------------------------------------

    hourly_physical = (
        residuals
        .set_index("timestamp")
        [
            [
                "load_error",
                "wind_on_error",
                "wind_off_error",
                "pv_error"
            ]
        ]
        .resample("1h")
        .sum()
        .reset_index()
    )

    hourly_physical["period"] = (
        hourly_physical["timestamp"]
        .apply(assign_period)
    )

    hourly_physical = hourly_physical[
        hourly_physical["period"] != "OUTSIDE"
    ].copy()

    # --------------------------------------------------------
    # 8. LOAD PRICE CALIBRATION
    # --------------------------------------------------------

    if not PRICE_CALIBRATION.exists():
        raise FileNotFoundError(
            f"Missing file:\n{PRICE_CALIBRATION}"
        )

    price = pd.read_csv(
        PRICE_CALIBRATION
    )

    required_price = [
        "timestamp",
        "period",
        "price_error"
    ]

    missing_price = [
        c for c in required_price
        if c not in price.columns
    ]

    if missing_price:
        raise ValueError(
            f"Price calibration missing columns: "
            f"{missing_price}"
        )

    price["timestamp"] = normalize_timestamp(
        price["timestamp"]
    )

    price["price_error"] = pd.to_numeric(
        price["price_error"],
        errors="coerce"
    )

    # Price is already hourly.
    # Do NOT use .dt.floor("h").
    price_hourly = (
        price[
            [
                "timestamp",
                "period",
                "price_error"
            ]
        ]
        .drop_duplicates("timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    print(
        f"Price residual rows: "
        f"{len(price_hourly):,}"
    )

    # --------------------------------------------------------
    # 9. MERGE HOURLY PHYSICAL + PRICE RESIDUALS
    # --------------------------------------------------------

    hourly = hourly_physical.merge(
        price_hourly[
            [
                "timestamp",
                "price_error"
            ]
        ],
        on="timestamp",
        how="inner",
        validate="one_to_one"
    )

    hourly = hourly[
        [
            "timestamp",
            "period",
            "price_error",
            "load_error",
            "wind_on_error",
            "wind_off_error",
            "pv_error"
        ]
    ].copy()

    hourly = (
        hourly
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # 10. QUALITY CHECKS
    # --------------------------------------------------------

    residual_columns = [
        "price_error",
        "load_error",
        "wind_on_error",
        "wind_off_error",
        "pv_error"
    ]

    missing_rates = {
        col: float(
            hourly[col].isna().mean()
        )
        for col in residual_columns
    }

    duplicate_hours = int(
        hourly["timestamp"].duplicated().sum()
    )

    print("\n----------------------------------------------")
    print("JOINT DATABASE QUALITY")
    print("----------------------------------------------")

    print(
        f"Hourly rows: "
        f"{len(hourly):,}"
    )

    print(
        f"Duplicate timestamps: "
        f"{duplicate_hours}"
    )

    for col, rate in missing_rates.items():
        print(
            f"{col:20s}: "
            f"{rate:.4%}"
        )

    # --------------------------------------------------------
    # 11. CORRELATION MATRIX
    # --------------------------------------------------------

    correlation = (
        hourly[
            residual_columns
        ]
        .corr()
    )

    # --------------------------------------------------------
    # 12. SUMMARY STATISTICS
    # --------------------------------------------------------

    summary = {}

    for col in residual_columns:

        series = (
            hourly[col]
            .dropna()
        )

        summary[col] = {
            "n": int(len(series)),
            "mean": float(series.mean()),
            "std": float(series.std()),
            "min": float(series.min()),
            "max": float(series.max()),
            "skewness": float(series.skew()),
            "kurtosis": float(series.kurt()),
        }

    # --------------------------------------------------------
    # 13. SAVE OUTPUTS
    # --------------------------------------------------------

    hourly.to_csv(
        OUTPUT_HOURLY,
        index=False,
        encoding="utf-8-sig"
    )

    correlation.to_csv(
        CORR_FILE,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # 14. STATUS
    # --------------------------------------------------------

    status = "PASS"

    if duplicate_hours > 0:
        status = "FAIL"

    if any(
        rate > 0.02
        for rate in missing_rates.values()
    ):
        status = "FAIL"

    # --------------------------------------------------------
    # 15. REPORT
    # --------------------------------------------------------

    report = {
        "gate": "10B.5",
        "status": status,
        "physical_15min_rows": int(
            len(residuals)
        ),
        "hourly_joint_rows": int(
            len(hourly)
        ),
        "duplicate_hourly_timestamps": duplicate_hours,
        "missing_rates": missing_rates,
        "summary": summary,
        "outputs": {
            "physical_15min": str(
                OUTPUT_15M
            ),
            "hourly_joint": str(
                OUTPUT_HOURLY
            ),
            "correlation": str(
                CORR_FILE
            )
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
    # 16. FINAL
    # --------------------------------------------------------

    print("\n==============================================")
    print(
        f" GATE 10B.5 STATUS: {status}"
    )
    print("==============================================")

    print(
        f"\n15-min database:\n{OUTPUT_15M}"
    )

    print(
        f"\nHourly joint database:\n{OUTPUT_HOURLY}"
    )

    print(
        f"\nCorrelation:\n{CORR_FILE}"
    )

    print(
        f"\nReport:\n{REPORT_FILE}"
    )

    if status == "PASS":

        print(
            "\n[PASS] Joint residual database is ready "
            "for Gate 10C."
        )

    else:

        print(
            "\n[STOP] Joint database quality checks failed."
        )


if __name__ == "__main__":
    main()

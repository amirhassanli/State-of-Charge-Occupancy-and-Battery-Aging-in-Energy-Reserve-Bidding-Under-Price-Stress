from pathlib import Path
import json

import numpy as np
import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

RAW = ROOT / "data" / "raw" / "smard"
OUT = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

OUT.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


# ============================================================
# REQUIRED FILES
# ============================================================

FILES = {
    "da_price": "da_price.csv",
    "load_actual": "load_actual.csv",
    "wind_on_actual": "wind_on_actual.csv",
    "wind_off_actual": "wind_off_actual.csv",
    "pv_actual": "pv_actual.csv",
    "residual_load_actual": "residual_load_actual.csv",
    "wind_on_forecast": "wind_on_forecast.csv",
    "wind_off_forecast": "wind_off_forecast.csv",
    "pv_forecast": "pv_forecast.csv",
}


# Expected row counts for the current core study period:
# 2024-01-01 -> 2025-09-30
#
# 15-min physical data: 61,340
# Hourly DA price:       15,335
#
# These are integrity checks for the dataset currently downloaded.
EXPECTED_PHYSICAL_ROWS = 61340
EXPECTED_PRICE_ROWS = 15335


# ============================================================
# LOAD ONE FILE
# ============================================================

def load_file(name: str, filename: str) -> pd.DataFrame:
    """
    Load one downloaded SMARD CSV and standardize its timestamp.

    Important:
    - Parse as UTC first.
    - Convert to Europe/Berlin afterward.
    - This avoids ambiguous DST parsing problems.
    """

    path = RAW / filename

    if not path.exists():
        raise FileNotFoundError(
            f"\nMissing required file:\n{path}\n"
            f"Please verify that the SMARD downloader completed successfully."
        )

    df = pd.read_csv(path)

    if "timestamp" not in df.columns:
        raise ValueError(
            f"{filename}: 'timestamp' column is missing."
        )

    # Convert safely through UTC.
    # This preserves DST transitions correctly.
    df["timestamp"] = (
        pd.to_datetime(
            df["timestamp"],
            utc=True,
            errors="coerce"
        )
        .dt.tz_convert("Europe/Berlin")
    )

    # Check invalid timestamps
    invalid_timestamp_count = int(df["timestamp"].isna().sum())

    if invalid_timestamp_count > 0:
        raise ValueError(
            f"{filename}: {invalid_timestamp_count} invalid timestamps found."
        )

    # Sort chronologically
    df = (
        df.sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# VALIDATE SINGLE SERIES
# ============================================================

def validate_single_series(
    name: str,
    df: pd.DataFrame
) -> dict:
    """
    Basic integrity checks for an individual SMARD series.
    """

    value_cols = [
        c for c in df.columns
        if c != "timestamp"
    ]

    report = {
        "name": name,
        "rows": int(len(df)),
        "duplicates": int(
            df["timestamp"].duplicated().sum()
        ),
        "missing_timestamp": int(
            df["timestamp"].isna().sum()
        ),
        "start": str(
            df["timestamp"].min()
        ),
        "end": str(
            df["timestamp"].max()
        ),
        "missing_value_rate": None,
        "negative_values": None,
    }

    if value_cols:
        value_col = value_cols[0]

        report["missing_value_rate"] = float(
            df[value_col].isna().mean()
        )

        report["negative_values"] = int(
            (df[value_col].dropna() < 0).sum()
        )

    return report


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print("       GATE 10A.1 — DATA VALIDATION")
    print("==============================================\n")

    # --------------------------------------------------------
    # 1. LOAD ALL FILES
    # --------------------------------------------------------

    data = {}
    reports = []

    for name, filename in FILES.items():

        df = load_file(
            name=name,
            filename=filename
        )

        data[name] = df

        r = validate_single_series(
            name=name,
            df=df
        )

        reports.append(r)

        missing_rate = r["missing_value_rate"]

        if missing_rate is None:
            missing_text = "N/A"
        else:
            missing_text = f"{missing_rate:.4%}"

        print(
            f"{name:25s}"
            f"{r['rows']:>8,} rows | "
            f"duplicates={r['duplicates']} | "
            f"missing={missing_text}"
        )

    # --------------------------------------------------------
    # 2. ROW COUNT CHECK
    # --------------------------------------------------------

    print("\n----------------------------------------------")
    print("ROW COUNT VALIDATION")
    print("----------------------------------------------")

    count_check = True

    for name in FILES:

        actual = len(data[name])

        if name == "da_price":
            expected = EXPECTED_PRICE_ROWS
        else:
            expected = EXPECTED_PHYSICAL_ROWS

        if actual != expected:

            count_check = False

            print(
                f"[WARNING] {name}: "
                f"expected={expected:,}, "
                f"actual={actual:,}"
            )

        else:

            print(
                f"[OK] {name}: "
                f"{actual:,} rows"
            )

    # --------------------------------------------------------
    # 3. DUPLICATE TIMESTAMP CHECK
    # --------------------------------------------------------

    duplicate_check = all(
        r["duplicates"] == 0
        for r in reports
    )

    print("\n----------------------------------------------")
    print("DUPLICATE TIMESTAMP CHECK")
    print("----------------------------------------------")

    if duplicate_check:
        print("[OK] No duplicate timestamps found.")
    else:
        print("[FAIL] Duplicate timestamps detected.")

    # --------------------------------------------------------
    # 4. MERGE ALL 15-MINUTE PHYSICAL DATA
    # --------------------------------------------------------

    physical_names = [
        "load_actual",
        "wind_on_actual",
        "wind_off_actual",
        "pv_actual",
        "residual_load_actual",
        "wind_on_forecast",
        "wind_off_forecast",
        "pv_forecast",
    ]

    merged = data[physical_names[0]].copy()

    for name in physical_names[1:]:

        merged = merged.merge(
            data[name],
            on="timestamp",
            how="outer",
            validate="one_to_one"
        )

    merged = (
        merged
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    print("\n----------------------------------------------")
    print("PHYSICAL DATA MERGE")
    print("----------------------------------------------")

    print(
        f"[OK] Merged physical dataset: "
        f"{len(merged):,} rows"
    )

    # --------------------------------------------------------
    # 5. PHYSICAL MISSINGNESS
    # --------------------------------------------------------

    missing_report = (
        merged
        .isna()
        .mean()
        .sort_values(ascending=False)
    )

    print("\n----------------------------------------------")
    print("MISSINGNESS")
    print("----------------------------------------------")

    print(missing_report)

    # Only original physical columns are relevant here.
    original_physical_columns = [
        "load_actual",
        "wind_on_actual",
        "wind_off_actual",
        "pv_actual",
        "residual_load_actual",
        "wind_on_forecast",
        "wind_off_forecast",
        "pv_forecast",
    ]

    max_missing = float(
        missing_report[
            [
                c for c in original_physical_columns
                if c in missing_report.index
            ]
        ].max()
    )

    # --------------------------------------------------------
    # 6. NEGATIVE PHYSICAL VALUES
    # --------------------------------------------------------

    physical_actual_columns = [
        "load_actual",
        "wind_on_actual",
        "wind_off_actual",
        "pv_actual",
    ]

    negative_report = {}

    for col in physical_actual_columns:

        negative_report[col] = int(
            (
                merged[col].dropna() < 0
            ).sum()
        )

    print("\n----------------------------------------------")
    print("NEGATIVE PHYSICAL VALUES")
    print("----------------------------------------------")

    for col, count in negative_report.items():

        if count == 0:
            print(f"[OK] {col}: 0")
        else:
            print(
                f"[WARNING] {col}: "
                f"{count:,} negative observations"
            )

    # --------------------------------------------------------
    # 7. RESIDUAL LOAD CONSISTENCY
    # --------------------------------------------------------

    print("\n----------------------------------------------")
    print("RESIDUAL-LOAD CONSISTENCY")
    print("----------------------------------------------")

    merged["residual_load_calculated"] = (
        merged["load_actual"]
        - merged["wind_on_actual"]
        - merged["wind_off_actual"]
        - merged["pv_actual"]
    )

    merged["residual_load_error"] = (
        merged["residual_load_actual"]
        - merged["residual_load_calculated"]
    )

    rl_error = (
        merged["residual_load_error"]
        .dropna()
    )

    if len(rl_error) == 0:

        residual_stats = {
            "mean_error": None,
            "median_error": None,
            "mae": None,
            "max_abs_error": None,
        }

        residual_check = False

        print(
            "[FAIL] No valid residual-load observations."
        )

    else:

        residual_stats = {
            "mean_error": float(
                rl_error.mean()
            ),
            "median_error": float(
                rl_error.median()
            ),
            "mae": float(
                np.abs(rl_error).mean()
            ),
            "max_abs_error": float(
                np.abs(rl_error).max()
            ),
        }

        # Current SMARD data show very small rounding differences.
        # We use a conservative tolerance of 0.05 MW.
        residual_check = (
            residual_stats["max_abs_error"] <= 0.05
        )

        print(
            f"Mean error       : "
            f"{residual_stats['mean_error']:.10f}"
        )

        print(
            f"Median error     : "
            f"{residual_stats['median_error']:.10f}"
        )

        print(
            f"MAE              : "
            f"{residual_stats['mae']:.10f}"
        )

        print(
            f"Maximum abs error: "
            f"{residual_stats['max_abs_error']:.10f}"
        )

        if residual_check:
            print(
                "[OK] Residual-load identity is consistent."
            )
        else:
            print(
                "[FAIL] Residual-load identity exceeded tolerance."
            )

    # --------------------------------------------------------
    # 8. DA PRICE VALIDATION
    # --------------------------------------------------------

    print("\n----------------------------------------------")
    print("DAY-AHEAD PRICE VALIDATION")
    print("----------------------------------------------")

    price = data["da_price"].copy()

    price_columns = [
        c for c in price.columns
        if c != "timestamp"
    ]

    if len(price_columns) != 1:

        raise ValueError(
            "DA price file should contain exactly one "
            "value column besides timestamp."
        )

    price_col = price_columns[0]

    price_values = price[price_col].dropna()

    if price_values.empty:
        raise ValueError(
            "DA price column contains no valid values."
        )

    negative_price_count = int(
        (price_values < 0).sum()
    )

    price_stats = {
        "rows": int(len(price)),
        "missing_rate": float(
            price[price_col].isna().mean()
        ),
        "negative_prices": negative_price_count,
        "min": float(price_values.min()),
        "max": float(price_values.max()),
        "mean": float(price_values.mean()),
        "std": float(price_values.std()),
    }

    print(
        f"Rows            : "
        f"{price_stats['rows']:,}"
    )

    print(
        f"Missing rate    : "
        f"{price_stats['missing_rate']:.4%}"
    )

    print(
        f"Negative prices : "
        f"{price_stats['negative_prices']:,}"
    )

    print(
        f"Minimum         : "
        f"{price_stats['min']:.4f}"
    )

    print(
        f"Maximum         : "
        f"{price_stats['max']:.4f}"
    )

    print(
        f"Mean            : "
        f"{price_stats['mean']:.4f}"
    )

    print(
        f"Std             : "
        f"{price_stats['std']:.4f}"
    )

    # --------------------------------------------------------
    # 9. SAVE PHYSICAL MASTER DATASET
    # --------------------------------------------------------

    physical_master = (
        OUT / "master_physical_15min.csv"
    )

    merged.to_csv(
        physical_master,
        index=False,
        encoding="utf-8-sig"
    )

    print("\n----------------------------------------------")
    print("MASTER PHYSICAL DATASET")
    print("----------------------------------------------")

    print(
        f"[SAVED] {physical_master}"
    )

    # --------------------------------------------------------
    # 10. SAVE DA PRICE MASTER
    # --------------------------------------------------------

    # IMPORTANT:
    # Do NOT call .dt.floor("h") here.
    #
    # The DA price file is already hourly.
    # Flooring timezone-aware Europe/Berlin timestamps can
    # trigger AmbiguousTimeError during the autumn DST switch.
    #
    # Therefore we preserve the original hourly timestamps.

    price_master = (
        OUT / "master_da_price_hourly.csv"
    )

    price_out = price.copy()

    price_out = price_out.rename(
        columns={
            price_col: "da_price_eur_mwh"
        }
    )

    price_out = (
        price_out[
            [
                "timestamp",
                "da_price_eur_mwh"
            ]
        ]
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    price_out.to_csv(
        price_master,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"[SAVED] {price_master}"
    )

    # --------------------------------------------------------
    # 11. FORECAST TIMING / LEAKAGE
    # --------------------------------------------------------

    # The current raw SMARD forecast CSVs do not contain
    # forecast_issued_at. Therefore this check is deliberately
    # marked PENDING instead of pretending that leakage has
    # already been proven to be zero.

    leakage_check = "PENDING"

    # --------------------------------------------------------
    # 12. FINAL GATE STATUS
    # --------------------------------------------------------

    status = "PASS"

    if not count_check:
        status = "FAIL"

    if not duplicate_check:
        status = "FAIL"

    if max_missing > 0.02:
        status = "FAIL"

    if not residual_check:
        status = "FAIL"

    # --------------------------------------------------------
    # 13. FINAL REPORT
    # --------------------------------------------------------

    report = {
        "gate": "10A.1",
        "status": status,
        "study_period": {
            "start": "2024-01-01",
            "end": "2025-09-30",
        },
        "row_count_check": bool(count_check),
        "duplicate_check": bool(duplicate_check),
        "max_missing_rate": max_missing,
        "negative_physical": negative_report,
        "negative_price_count": negative_price_count,
        "price_stats": price_stats,
        "residual_load_check": residual_stats,
        "residual_load_check_pass": bool(
            residual_check
        ),
        "leakage_check": leakage_check,
        "physical_master": str(
            physical_master
        ),
        "price_master": str(
            price_master
        ),
    }

    report_path = (
        REPORTS /
        "gate10a_validation.json"
    )

    with open(
        report_path,
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
    # 14. FINAL CONSOLE OUTPUT
    # --------------------------------------------------------

    print("\n==============================================")
    print(
        f"GATE 10A.1 STATUS: {status}"
    )
    print("==============================================")

    print(
        f"\nValidation report:\n{report_path}"
    )

    if status == "PASS":

        print(
            "\n[PASS] Gate 10A.1 validation completed."
        )

        print(
            "\nMaster datasets:"
        )

        print(
            f"  {physical_master}"
        )

        print(
            f"  {price_master}"
        )

        print(
            "\nNext checkpoint: GATE 10A.2"
        )
        print(
            "Forecast timing + leakage firewall."
        )

    else:

        print(
            "\n[STOP] Gate 10A.1 FAILED."
        )

        print(
            "Do NOT proceed to forecast calibration."
        )

        print(
            "Inspect gate10a_validation.json."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

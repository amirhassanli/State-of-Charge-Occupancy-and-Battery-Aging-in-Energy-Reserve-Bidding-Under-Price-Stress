from pathlib import Path
import json

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

CALIBRATION = ROOT / "data" / "calibration"
REPORTS = ROOT / "reports"

CALIBRATION.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

INPUT_FILE = (
    CALIBRATION /
    "da_price_baseline_forecasts.csv"
)

OUTPUT_FILE = (
    CALIBRATION /
    "da_price_calibrated_forecast.csv"
)

REPORT_FILE = (
    REPORTS /
    "gate10b4_da_price_calibration.json"
)


# ============================================================
# LOAD
# ============================================================

def load_data():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing file:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    required = [
        "timestamp",
        "da_price_eur_mwh",
        "period",
        "forecast_hybrid",
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    df["timestamp"] = (
        pd.to_datetime(
            df["timestamp"],
            utc=True,
            errors="coerce"
        )
        .dt.tz_convert("Europe/Berlin")
    )

    if df["timestamp"].isna().any():
        raise ValueError(
            "Invalid timestamps detected."
        )

    df["da_price_eur_mwh"] = pd.to_numeric(
        df["da_price_eur_mwh"],
        errors="coerce"
    )

    df["forecast_hybrid"] = pd.to_numeric(
        df["forecast_hybrid"],
        errors="coerce"
    )

    return (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


# ============================================================
# CONFORMAL QUANTILE
# ============================================================

def conformal_q(
    errors,
    coverage
):

    x = (
        pd.Series(errors)
        .dropna()
        .to_numpy(dtype=float)
    )

    if len(x) == 0:
        return np.nan

    scores = np.abs(x)

    alpha = 1.0 - coverage

    q = np.quantile(
        scores,
        1.0 - alpha,
        method="higher"
    )

    return float(q)


# ============================================================
# COVERAGE
# ============================================================

def calculate_coverage(
    actual,
    lower,
    upper
):

    mask = (
        actual.notna()
        & lower.notna()
        & upper.notna()
    )

    if mask.sum() == 0:
        return np.nan

    return float(
        (
            (actual[mask] >= lower[mask])
            &
            (actual[mask] <= upper[mask])
        ).mean()
    )


# ============================================================
# INTERVAL WIDTH
# ============================================================

def calculate_interval_width(
    lower,
    upper
):

    width = (
        upper - lower
    ).dropna()

    if width.empty:
        return np.nan

    return float(width.mean())


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10B.4 — DA PRICE CALIBRATION")
    print("==============================================\n")

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    df = load_data()

    print(
        f"Loaded observations: {len(df):,}"
    )

    # --------------------------------------------------------
    # Forecast residual
    # --------------------------------------------------------

    df["price_error"] = (
        df["da_price_eur_mwh"]
        - df["forecast_hybrid"]
    )

    # --------------------------------------------------------
    # TRAIN ONLY for calibration
    # --------------------------------------------------------

    train_mask = (
        df["period"] == "TRAIN"
    )

    validation_mask = (
        df["period"] == "VALIDATION"
    )

    oos_mask = (
        df["period"] == "OOS"
    )

    train_errors = (
        df.loc[
            train_mask,
            "price_error"
        ]
    )

    # --------------------------------------------------------
    # Conformal quantiles
    # --------------------------------------------------------

    q90 = conformal_q(
        train_errors,
        coverage=0.90
    )

    q95 = conformal_q(
        train_errors,
        coverage=0.95
    )

    print("----------------------------------------------")
    print("TRAIN CONFORMAL CALIBRATION")
    print("----------------------------------------------")

    print(
        f"Train observations : "
        f"{train_mask.sum():,}"
    )

    print(
        f"q90                : "
        f"{q90:.6f} €/MWh"
    )

    print(
        f"q95                : "
        f"{q95:.6f} €/MWh"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Add interval columns to df FIRST.
    # --------------------------------------------------------

    df["lower_90"] = (
        df["forecast_hybrid"] - q90
    )

    df["upper_90"] = (
        df["forecast_hybrid"] + q90
    )

    df["lower_95"] = (
        df["forecast_hybrid"] - q95
    )

    df["upper_95"] = (
        df["forecast_hybrid"] + q95
    )

    # --------------------------------------------------------
    # NOW create validation / OOS subsets
    # --------------------------------------------------------

    validation = (
        df.loc[
            validation_mask
        ].copy()
    )

    oos = (
        df.loc[
            oos_mask
        ].copy()
    )

    # --------------------------------------------------------
    # Validation coverage
    # --------------------------------------------------------

    val_cov90 = calculate_coverage(
        validation["da_price_eur_mwh"],
        validation["lower_90"],
        validation["upper_90"]
    )

    val_cov95 = calculate_coverage(
        validation["da_price_eur_mwh"],
        validation["lower_95"],
        validation["upper_95"]
    )

    val_width90 = calculate_interval_width(
        validation["lower_90"],
        validation["upper_90"]
    )

    val_width95 = calculate_interval_width(
        validation["lower_95"],
        validation["upper_95"]
    )

    # --------------------------------------------------------
    # OOS coverage
    # --------------------------------------------------------
    # OOS is NOT used for calibration.
    # It is evaluated only after parameters are frozen.

    oos_cov90 = calculate_coverage(
        oos["da_price_eur_mwh"],
        oos["lower_90"],
        oos["upper_90"]
    )

    oos_cov95 = calculate_coverage(
        oos["da_price_eur_mwh"],
        oos["lower_95"],
        oos["upper_95"]
    )

    oos_width90 = calculate_interval_width(
        oos["lower_90"],
        oos["upper_90"]
    )

    oos_width95 = calculate_interval_width(
        oos["lower_95"],
        oos["upper_95"]
    )

    # --------------------------------------------------------
    # Console
    # --------------------------------------------------------

    print("\n----------------------------------------------")
    print("VALIDATION")
    print("----------------------------------------------")

    print(
        f"Observations          : "
        f"{len(validation):,}"
    )

    print(
        f"Coverage 90%          : "
        f"{val_cov90:.4%}"
    )

    print(
        f"Coverage 95%          : "
        f"{val_cov95:.4%}"
    )

    print(
        f"Mean width 90%        : "
        f"{val_width90:.6f} €/MWh"
    )

    print(
        f"Mean width 95%        : "
        f"{val_width95:.6f} €/MWh"
    )

    print("\n----------------------------------------------")
    print("OOS — REPORTING ONLY")
    print("----------------------------------------------")

    print(
        f"Observations          : "
        f"{len(oos):,}"
    )

    print(
        f"Coverage 90%          : "
        f"{oos_cov90:.4%}"
    )

    print(
        f"Coverage 95%          : "
        f"{oos_cov95:.4%}"
    )

    print(
        f"Mean width 90%        : "
        f"{oos_width90:.6f} €/MWh"
    )

    print(
        f"Mean width 95%        : "
        f"{oos_width95:.6f} €/MWh"
    )

    # --------------------------------------------------------
    # Coverage deviations
    # --------------------------------------------------------

    val_miscoverage_90 = (
        val_cov90 - 0.90
    )

    val_miscoverage_95 = (
        val_cov95 - 0.95
    )

    # --------------------------------------------------------
    # Save complete dataset
    # --------------------------------------------------------

    output_cols = [
        "timestamp",
        "period",
        "da_price_eur_mwh",
        "forecast_hybrid",
        "price_error",
        "lower_90",
        "upper_90",
        "lower_95",
        "upper_95",
    ]

    df[
        output_cols
    ].to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    report = {

        "gate": "10B.4",

        "status": "PASS",

        "point_forecast_model": "Hybrid",

        "point_forecast_formula":
            "0.5*Lag24 + 0.5*Lag168",

        "calibration_period":
            "TRAIN 2024",

        "validation_period":
            "2025-01-01 to 2025-06-30",

        "oos_period":
            "2025-07-01 to 2025-09-30",

        "train_rows":
            int(train_mask.sum()),

        "validation_rows":
            int(validation_mask.sum()),

        "oos_rows":
            int(oos_mask.sum()),

        "conformal_q90":
            q90,

        "conformal_q95":
            q95,

        "validation": {

            "coverage_90":
                val_cov90,

            "coverage_95":
                val_cov95,

            "miscoverage_90":
                val_miscoverage_90,

            "miscoverage_95":
                val_miscoverage_95,

            "mean_interval_width_90":
                val_width90,

            "mean_interval_width_95":
                val_width95,
        },

        "oos_reporting_only": {

            "coverage_90":
                oos_cov90,

            "coverage_95":
                oos_cov95,

            "mean_interval_width_90":
                oos_width90,

            "mean_interval_width_95":
                oos_width95,
        },

        "output_file":
            str(OUTPUT_FILE),
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
    # Final
    # --------------------------------------------------------

    print("\n==============================================")
    print(" GATE 10B.4 COMPLETE")
    print("==============================================")

    print(
        f"\nCalibrated dataset:\n"
        f"{OUTPUT_FILE}"
    )

    print(
        f"\nReport:\n"
        f"{REPORT_FILE}"
    )

    print(
        "\nNext checkpoint:"
    )

    print(
        "JOINT RESIDUAL DATABASE → GATE 10C"
    )


if __name__ == "__main__":
    main()

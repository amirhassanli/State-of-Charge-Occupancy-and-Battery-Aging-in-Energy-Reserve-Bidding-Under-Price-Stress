from pathlib import Path
import json

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
CALIBRATION = ROOT / "data" / "calibration"

REPORTS.mkdir(parents=True, exist_ok=True)
CALIBRATION.mkdir(parents=True, exist_ok=True)


MASTER_FILE = PROCESSED / "master_information_set.csv"


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


# ============================================================
# LOAD MASTER DATA
# ============================================================

def load_master():

    if not MASTER_FILE.exists():
        raise FileNotFoundError(
            f"Missing file:\n{MASTER_FILE}"
        )

    df = pd.read_csv(MASTER_FILE)

    if "timestamp" not in df.columns:
        raise ValueError(
            "timestamp column missing."
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

    return (
        df.sort_values("timestamp")
        .reset_index(drop=True)
    )


# ============================================================
# PERIOD LABEL
# ============================================================

def assign_period(ts):

    if TRAIN_START <= ts <= TRAIN_END:
        return "TRAIN"

    if VAL_START <= ts <= VAL_END:
        return "VALIDATION"

    if OOS_START <= ts <= OOS_END:
        return "OOS"

    return "OUTSIDE"


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(actual, forecast):

    mask = (
        actual.notna()
        & forecast.notna()
    )

    y = actual[mask].to_numpy(dtype=float)
    f = forecast[mask].to_numpy(dtype=float)

    if len(y) == 0:
        return {
            "n": 0,
            "MAE": np.nan,
            "RMSE": np.nan,
            "Bias": np.nan,
            "nMAE": np.nan,
        }

    error = y - f

    mae = np.mean(np.abs(error))
    rmse = np.sqrt(np.mean(error ** 2))
    bias = np.mean(error)

    mean_abs_actual = np.mean(np.abs(y))

    if mean_abs_actual > 0:
        nmae = mae / mean_abs_actual * 100.0
    else:
        nmae = np.nan

    return {
        "n": int(len(y)),
        "MAE": float(mae),
        "RMSE": float(rmse),
        "Bias": float(bias),
        "nMAE_percent": float(nmae)
        if not np.isnan(nmae)
        else np.nan,
    }


# ============================================================
# CONFORMAL QUANTILE
# ============================================================

def conformal_quantile(
    train_errors,
    coverage=0.90
):

    errors = pd.Series(train_errors).dropna()

    if errors.empty:
        return np.nan

    scores = np.abs(
        errors.to_numpy(dtype=float)
    )

    alpha = 1.0 - coverage

    # Conservative finite-sample quantile.
    q = np.quantile(
        scores,
        1.0 - alpha,
        method="higher"
    )

    return float(q)


# ============================================================
# APPLY CALIBRATION
# ============================================================

def calibrate_series(
    df,
    actual_col,
    forecast_col,
    name
):

    temp = df[
        [
            "timestamp",
            actual_col,
            forecast_col
        ]
    ].copy()

    temp["period"] = temp["timestamp"].apply(
        assign_period
    )

    temp["error"] = (
        temp[actual_col]
        - temp[forecast_col]
    )

    # --------------------------------------------------------
    # TRAIN metrics
    # --------------------------------------------------------

    train = temp[
        temp["period"] == "TRAIN"
    ].copy()

    validation = temp[
        temp["period"] == "VALIDATION"
    ].copy()

    oos = temp[
        temp["period"] == "OOS"
    ].copy()

    train_metrics = calculate_metrics(
        train[actual_col],
        train[forecast_col]
    )

    validation_metrics = calculate_metrics(
        validation[actual_col],
        validation[forecast_col]
    )

    # --------------------------------------------------------
    # Conformal calibration
    # --------------------------------------------------------

    q90 = conformal_quantile(
        train["error"],
        coverage=0.90
    )

    q95 = conformal_quantile(
        train["error"],
        coverage=0.95
    )

    # --------------------------------------------------------
    # Apply intervals
    # --------------------------------------------------------

    for target in [
        train,
        validation,
        oos
    ]:

        target["lower_90"] = (
            target[forecast_col] - q90
        )

        target["upper_90"] = (
            target[forecast_col] + q90
        )

        target["lower_95"] = (
            target[forecast_col] - q95
        )

        target["upper_95"] = (
            target[forecast_col] + q95
        )

    # --------------------------------------------------------
    # Validation coverage
    # --------------------------------------------------------

    def coverage(actual, lower, upper):

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

    val_cov90 = coverage(
        validation[actual_col],
        validation["lower_90"],
        validation["upper_90"]
    )

    val_cov95 = coverage(
        validation[actual_col],
        validation["lower_95"],
        validation["upper_95"]
    )

    result = pd.concat(
        [train, validation, oos],
        ignore_index=True
    )

    result["variable"] = name

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    output_file = (
        CALIBRATION
        / f"{name}_calibration.csv"
    )

    result.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    metrics = {
        "variable": name,
        "train": train_metrics,
        "validation": validation_metrics,
        "conformal_q90": q90,
        "conformal_q95": q95,
        "validation_coverage_90": val_cov90,
        "validation_coverage_95": val_cov95,
        "output": str(output_file),
    }

    return metrics


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10B — FORECAST CALIBRATION")
    print("==============================================\n")

    df = load_master()

    print(
        f"Master dataset loaded: "
        f"{len(df):,} rows"
    )

    # --------------------------------------------------------
    # Variables
    # --------------------------------------------------------

    calibration_targets = {

        # DA-eligible
        "load": (
            "load_actual",
            "load_forecast"
        ),

        # Intraday renewable forecasts
        "wind_onshore": (
            "wind_on_actual",
            "wind_on_forecast"
        ),

        "wind_offshore": (
            "wind_off_actual",
            "wind_off_forecast"
        ),

        "pv": (
            "pv_actual",
            "pv_forecast"
        ),
    }

    all_results = []

    for name, (
        actual_col,
        forecast_col
    ) in calibration_targets.items():

        print("\n----------------------------------------------")
        print(
            f"CALIBRATING: {name}"
        )
        print("----------------------------------------------")

        if actual_col not in df.columns:
            print(
                f"[SKIP] Missing actual column: "
                f"{actual_col}"
            )
            continue

        if forecast_col not in df.columns:
            print(
                f"[SKIP] Missing forecast column: "
                f"{forecast_col}"
            )
            continue

        result = calibrate_series(
            df=df,
            actual_col=actual_col,
            forecast_col=forecast_col,
            name=name
        )

        all_results.append(result)

        print(
            f"TRAIN MAE: "
            f"{result['train']['MAE']:.6f}"
        )

        print(
            f"VALIDATION MAE: "
            f"{result['validation']['MAE']:.6f}"
        )

        print(
            f"90% conformal q: "
            f"{result['conformal_q90']:.6f}"
        )

        print(
            f"95% conformal q: "
            f"{result['conformal_q95']:.6f}"
        )

        print(
            f"Validation coverage 90%: "
            f"{result['validation_coverage_90']:.4%}"
        )

        print(
            f"Validation coverage 95%: "
            f"{result['validation_coverage_95']:.4%}"
        )

    # --------------------------------------------------------
    # Save metrics database
    # --------------------------------------------------------

    metrics_file = (
        REPORTS
        / "gate10b_forecast_metrics.json"
    )

    with open(
        metrics_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "gate": "10B",
                "status": "PASS",
                "results": all_results,
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    print("\n==============================================")
    print(" GATE 10B INITIAL CALIBRATION COMPLETE")
    print("==============================================")

    print(
        f"\nMetrics report:\n{metrics_file}"
    )

    print(
        "\nImportant:"
    )

    print(
        "Load forecast is eligible for the DA information set."
    )

    print(
        "Wind/PV forecasts are reserved for Intraday stages."
    )

    print(
        "\nNext checkpoint:"
    )

    print(
        "GATE 10B.3 — DA PRICE FORECAST"
    )


if __name__ == "__main__":
    main()
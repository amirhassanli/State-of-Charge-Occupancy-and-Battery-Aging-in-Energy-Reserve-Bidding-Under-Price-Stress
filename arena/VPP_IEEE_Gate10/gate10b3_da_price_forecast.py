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

CALIBRATION.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

PRICE_FILE = PROCESSED / "master_da_price_hourly.csv"


# ============================================================
# STUDY PERIODS
# ============================================================

TRAIN_START = pd.Timestamp(
    "2024-01-01",
    tz="Europe/Berlin"
)

TRAIN_END = pd.Timestamp(
    "2024-12-31 23:00",
    tz="Europe/Berlin"
)

VAL_START = pd.Timestamp(
    "2025-01-01",
    tz="Europe/Berlin"
)

VAL_END = pd.Timestamp(
    "2025-06-30 23:00",
    tz="Europe/Berlin"
)

OOS_START = pd.Timestamp(
    "2025-07-01",
    tz="Europe/Berlin"
)

OOS_END = pd.Timestamp(
    "2025-09-30 23:00",
    tz="Europe/Berlin"
)


# ============================================================
# LOAD PRICE DATA
# ============================================================

def load_price():

    if not PRICE_FILE.exists():
        raise FileNotFoundError(
            f"Missing price dataset:\n{PRICE_FILE}"
        )

    df = pd.read_csv(PRICE_FILE)

    if "timestamp" not in df.columns:
        raise ValueError(
            "timestamp column missing."
        )

    if "da_price_eur_mwh" not in df.columns:
        raise ValueError(
            "da_price_eur_mwh column missing."
        )

    df["timestamp"] = (
        pd.to_datetime(
            df["timestamp"],
            utc=True,
            errors="coerce"
        )
        .dt.tz_convert("Europe/Berlin")
    )

    df["da_price_eur_mwh"] = pd.to_numeric(
        df["da_price_eur_mwh"],
        errors="coerce"
    )

    if df["timestamp"].isna().any():
        raise ValueError(
            "Invalid price timestamps detected."
        )

    df = (
        df
        .sort_values("timestamp")
        .drop_duplicates("timestamp")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# PERIOD LABEL
# ============================================================

def label_period(ts):

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

def metrics(actual, forecast):

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
            "sMAPE": np.nan,
        }

    error = y - f

    mae = np.mean(np.abs(error))

    rmse = np.sqrt(
        np.mean(error ** 2)
    )

    bias = np.mean(error)

    denominator = (
        np.abs(y) + np.abs(f)
    )

    valid = denominator > 0

    if valid.any():

        smape = np.mean(
            2.0
            * np.abs(y[valid] - f[valid])
            / denominator[valid]
        ) * 100.0

    else:

        smape = np.nan

    return {
        "n": int(len(y)),
        "MAE": float(mae),
        "RMSE": float(rmse),
        "Bias": float(bias),
        "sMAPE_percent": float(smape),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10B.3 — DA PRICE FORECAST")
    print("==============================================\n")

    df = load_price()

    print(
        f"Loaded price observations: "
        f"{len(df):,}"
    )

    # --------------------------------------------------------
    # Create lag forecasts
    # --------------------------------------------------------

    # Previous day, same hour
    df["forecast_lag24"] = (
        df["da_price_eur_mwh"]
        .shift(24)
    )

    # Previous week, same hour
    df["forecast_lag168"] = (
        df["da_price_eur_mwh"]
        .shift(168)
    )

    # Hybrid seasonal baseline
    df["forecast_hybrid"] = (
        df["forecast_lag24"]
        + df["forecast_lag168"]
    ) / 2.0

    # --------------------------------------------------------
    # Period
    # --------------------------------------------------------

    df["period"] = df["timestamp"].apply(
        label_period
    )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    models = {
        "Lag24": "forecast_lag24",
        "Lag168": "forecast_lag168",
        "Hybrid": "forecast_hybrid",
    }

    all_metrics = []

    for model_name, forecast_col in models.items():

        print("\n----------------------------------------------")
        print(model_name)
        print("----------------------------------------------")

        for period_name in [
            "TRAIN",
            "VALIDATION",
            "OOS"
        ]:

            subset = (
                df[df["period"] == period_name]
                .copy()
            )

            result = metrics(
                subset["da_price_eur_mwh"],
                subset[forecast_col]
            )

            result["model"] = model_name
            result["period"] = period_name

            all_metrics.append(result)

            print(
                f"{period_name:12s} "
                f"N={result['n']:5d} | "
                f"MAE={result['MAE']:.4f} | "
                f"RMSE={result['RMSE']:.4f} | "
                f"Bias={result['Bias']:.4f} | "
                f"sMAPE={result['sMAPE_percent']:.2f}%"
            )

    metrics_df = pd.DataFrame(
        all_metrics
    )

    # --------------------------------------------------------
    # Select best model based on validation MAE
    # --------------------------------------------------------

    validation = metrics_df[
        metrics_df["period"] == "VALIDATION"
    ].copy()

    validation = validation.sort_values(
        "MAE"
    )

    best_model = validation.iloc[0]["model"]

    best_forecast_col = models[best_model]

    print("\n==============================================")
    print(" VALIDATION MODEL SELECTION")
    print("==============================================")

    print(
        f"Best baseline: {best_model}"
    )

    print(
        f"Validation MAE: "
        f"{validation.iloc[0]['MAE']:.6f}"
    )

    # --------------------------------------------------------
    # Save all forecasts
    # --------------------------------------------------------

    output_cols = [
        "timestamp",
        "da_price_eur_mwh",
        "period",
        "forecast_lag24",
        "forecast_lag168",
        "forecast_hybrid",
    ]

    forecast_file = (
        CALIBRATION /
        "da_price_baseline_forecasts.csv"
    )

    df[output_cols].to_csv(
        forecast_file,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Save metrics
    # --------------------------------------------------------

    metrics_file = (
        REPORTS /
        "gate10b3_da_price_baseline_metrics.csv"
    )

    metrics_df.to_csv(
        metrics_file,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Save report
    # --------------------------------------------------------

    report = {
        "gate": "10B.3",
        "status": "PASS",
        "best_baseline": best_model,
        "validation_metrics": (
            validation
            .to_dict(orient="records")
        ),
        "forecast_file": str(
            forecast_file
        ),
        "metrics_file": str(
            metrics_file
        ),
    }

    report_file = (
        REPORTS /
        "gate10b3_da_price_report.json"
    )

    with open(
        report_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("\n==============================================")
    print(" GATE 10B.3 BASELINE COMPLETE")
    print("==============================================")

    print(
        f"\nForecasts:\n{forecast_file}"
    )

    print(
        f"\nMetrics:\n{metrics_file}"
    )

    print(
        f"\nReport:\n{report_file}"
    )

    print(
        "\nNext: build calibrated DA-price model."
    )


if __name__ == "__main__":
    main()
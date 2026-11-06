from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent

PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

MASTER_FILE = PROCESSED / "load_forecast_derived_from_smard.csv"


def main():

    print("\n==============================================")
    print(" LOAD FORECAST CONSISTENCY CHECK")
    print("==============================================\n")

    if not MASTER_FILE.exists():
        raise FileNotFoundError(MASTER_FILE)

    df = pd.read_csv(MASTER_FILE)

    df["timestamp"] = (
        pd.to_datetime(
            df["timestamp"],
            utc=True,
            errors="coerce"
        )
        .dt.tz_convert("Europe/Berlin")
    )

    required = [
        "timestamp",
        "load_forecast",
        "residual_load_forecast",
        "wind_on_forecast",
        "wind_off_forecast",
        "pv_forecast",
    ]

    missing_cols = [
        c for c in required
        if c not in df.columns
    ]

    if missing_cols:
        raise ValueError(
            f"Missing columns: {missing_cols}"
        )

    # Reconstruct residual load independently
    residual_reconstructed = (
        df["load_forecast"]
        - df["wind_on_forecast"]
        - df["wind_off_forecast"]
        - df["pv_forecast"]
    )

    error = (
        df["residual_load_forecast"]
        - residual_reconstructed
    )

    error = error.dropna()

    mae = float(np.abs(error).mean())
    max_abs = float(np.abs(error).max())
    mean_error = float(error.mean())

    report = {
        "rows": int(len(df)),
        "missing_rate": float(
            df[required[1:]].isna().any(axis=1).mean()
        ),
        "mean_error": mean_error,
        "mae": mae,
        "max_abs_error": max_abs,
        "status": "PASS" if max_abs <= 0.05 else "FAIL",
    }

    print("----------------------------------------------")
    print("RESULT")
    print("----------------------------------------------")

    print(f"Rows              : {report['rows']:,}")
    print(f"Missing rate      : {report['missing_rate']:.4%}")
    print(f"Mean error        : {mean_error:.10f}")
    print(f"MAE               : {mae:.10f}")
    print(f"Maximum abs error : {max_abs:.10f}")
    print(f"STATUS            : {report['status']}")

    output = REPORTS / "load_forecast_consistency_report.json"

    with open(
        output,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"\nReport saved:\n{output}")

    if report["status"] == "PASS":
        print(
            "\n[PASS] Load forecast is internally "
            "consistent with SMARD residual-load identity."
        )
    else:
        print(
            "\n[FAIL] Do not continue to calibration."
        )


if __name__ == "__main__":
    main()
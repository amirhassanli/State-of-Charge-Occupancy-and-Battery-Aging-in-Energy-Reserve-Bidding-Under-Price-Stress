from pathlib import Path
import json
import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parent

RAW = ROOT / "data" / "raw" / "smard"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

PROCESSED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


def load_series(filename, value_name):
    path = RAW / filename

    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    df = pd.read_csv(path)

    if "timestamp" not in df.columns:
        raise ValueError(f"{filename}: timestamp column missing")

    value_cols = [c for c in df.columns if c != "timestamp"]

    if len(value_cols) != 1:
        raise ValueError(
            f"{filename}: expected exactly one value column, "
            f"found {value_cols}"
        )

    df = df.rename(columns={value_cols[0]: value_name})

    df["timestamp"] = (
        pd.to_datetime(
            df["timestamp"],
            utc=True,
            errors="coerce"
        )
        .dt.tz_convert("Europe/Berlin")
    )

    df[value_name] = pd.to_numeric(
        df[value_name],
        errors="coerce"
    )

    return (
        df[
            ["timestamp", value_name]
        ]
        .sort_values("timestamp")
        .drop_duplicates("timestamp")
        .reset_index(drop=True)
    )


def main():

    print("\n==============================================")
    print(" DERIVE LOAD FORECAST FROM SMARD FORECASTS")
    print("==============================================\n")

    # --------------------------------------------------------
    # Load forecast residual load
    # --------------------------------------------------------

    residual = load_series(
        "forecast_residual_load.csv",
        "residual_load_forecast"
    )

    # --------------------------------------------------------
    # Existing renewable forecasts
    # --------------------------------------------------------

    wind_on = load_series(
        "wind_on_forecast.csv",
        "wind_on_forecast"
    )

    wind_off = load_series(
        "wind_off_forecast.csv",
        "wind_off_forecast"
    )

    pv = load_series(
        "pv_forecast.csv",
        "pv_forecast"
    )

    # --------------------------------------------------------
    # Merge
    # --------------------------------------------------------

    df = residual.merge(
        wind_on,
        on="timestamp",
        how="inner",
        validate="one_to_one"
    )

    df = df.merge(
        wind_off,
        on="timestamp",
        how="inner",
        validate="one_to_one"
    )

    df = df.merge(
        pv,
        on="timestamp",
        how="inner",
        validate="one_to_one"
    )

    # --------------------------------------------------------
    # Derive forecast load
    #
    # SMARD definition:
    #
    # forecast residual load =
    # forecast load
    # - forecast wind onshore
    # - forecast wind offshore
    # - forecast PV
    #
    # Therefore:
    #
    # forecast load =
    # residual forecast
    # + wind onshore forecast
    # + wind offshore forecast
    # + PV forecast
    # --------------------------------------------------------

    df["load_forecast"] = (
        df["residual_load_forecast"]
        + df["wind_on_forecast"]
        + df["wind_off_forecast"]
        + df["pv_forecast"]
    )

    # --------------------------------------------------------
    # Quality checks
    # --------------------------------------------------------

    missing_rate = float(
        df["load_forecast"].isna().mean()
    )

    negative_count = int(
        (df["load_forecast"].dropna() < 0).sum()
    )

    print("----------------------------------------------")
    print("RESULT")
    print("----------------------------------------------")

    print(
        f"Rows           : {len(df):,}"
    )

    print(
        f"Missing rate   : {missing_rate:.4%}"
    )

    print(
        f"Negative loads : {negative_count}"
    )

    print(
        f"Start          : {df['timestamp'].min()}"
    )

    print(
        f"End            : {df['timestamp'].max()}"
    )

    # --------------------------------------------------------
    # Save standardized forecast dataset
    # --------------------------------------------------------

    output = df[
        [
            "timestamp",
            "load_forecast",
            "residual_load_forecast",
            "wind_on_forecast",
            "wind_off_forecast",
            "pv_forecast",
        ]
    ].copy()

    output_file = (
        PROCESSED /
        "load_forecast_derived_from_smard.csv"
    )

    output.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    report = {
        "method":
            "load_forecast = "
            "residual_load_forecast + "
            "wind_on_forecast + "
            "wind_off_forecast + "
            "pv_forecast",

        "source":
            "Bundesnetzagentur | SMARD.de",

        "rows": int(len(output)),

        "missing_rate": missing_rate,

        "negative_values": negative_count,

        "start": str(output["timestamp"].min()),

        "end": str(output["timestamp"].max()),

        "output_file": str(output_file),
    }

    report_file = (
        REPORTS /
        "load_forecast_derivation_report.json"
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
    print(" LOAD FORECAST DERIVATION COMPLETE")
    print("==============================================")

    print(
        f"\nSaved:\n{output_file}"
    )

    print(
        f"\nReport:\n{report_file}"
    )


if __name__ == "__main__":
    main()
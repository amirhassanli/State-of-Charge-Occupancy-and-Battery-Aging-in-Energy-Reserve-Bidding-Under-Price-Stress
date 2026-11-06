from pathlib import Path
import pandas as pd
import json


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

RAW = ROOT / "data" / "raw" / "smard"

SOURCE = RAW / "load_forecast_raw_response.bin"
OUTPUT = RAW / "forecast_residual_load.csv"
REPORT = RAW / "forecast_residual_load_conversion_report.json"


# ============================================================
# CHECK SOURCE
# ============================================================

if not SOURCE.exists():
    raise FileNotFoundError(
        f"Raw SMARD file not found:\n{SOURCE}"
    )


print("\n==============================================")
print(" CONVERT SMARD FORECASTED RESIDUAL LOAD")
print("==============================================\n")

print(f"Reading:\n{SOURCE}")


# ============================================================
# READ SMARD CSV
# ============================================================

df = pd.read_csv(
    SOURCE,
    sep=";",
    engine="python"
)

print("\nOriginal columns:")
for col in df.columns:
    print(f"  - {col}")

print(f"\nRows: {len(df):,}")


# ============================================================
# EXPECTED STRUCTURE
# ============================================================

if len(df.columns) < 3:
    raise ValueError(
        "Unexpected SMARD file structure."
    )

df = df.iloc[:, :3].copy()

df.columns = [
    "start_date",
    "end_date",
    "residual_load_forecast"
]


# ============================================================
# PARSE NUMERIC VALUES
# ============================================================
# IMPORTANT:
# SMARD uses thousands separators such as:
# 1,310.25
#
# Therefore remove commas BEFORE numeric conversion.
# ============================================================

df["residual_load_forecast"] = (
    df["residual_load_forecast"]
    .astype(str)
    .str.replace(",", "", regex=False)
    .str.strip()
)

df["residual_load_forecast"] = pd.to_numeric(
    df["residual_load_forecast"],
    errors="coerce"
)


# ============================================================
# PARSE TIMESTAMP
# ============================================================
# pandas 2.2+ supports format="mixed".
# This avoids the previous warning caused by
# slightly different date-string formatting.
# ============================================================

df["timestamp"] = pd.to_datetime(
    df["start_date"],
    format="mixed",
    errors="coerce"
)


if df["timestamp"].isna().any():

    bad = int(
        df["timestamp"].isna().sum()
    )

    raise ValueError(
        f"{bad} invalid timestamps found."
    )


# SMARD timestamps are local German time.
#
# We use Europe/Berlin and explicitly handle DST.
#
# Ambiguous fall-back times are kept in chronological order.
# ============================================================

df["timestamp"] = (
    df["timestamp"]
    .dt.tz_localize(
        "Europe/Berlin",
        ambiguous="infer",
        nonexistent="shift_forward"
    )
)


# ============================================================
# STANDARDIZED OUTPUT
# ============================================================

result = df[
    [
        "timestamp",
        "residual_load_forecast"
    ]
].copy()


result = (
    result
    .sort_values("timestamp")
    .reset_index(drop=True)
)


# ============================================================
# DUPLICATES
# ============================================================

duplicate_count = int(
    result["timestamp"].duplicated().sum()
)

if duplicate_count > 0:

    print(
        f"[WARNING] {duplicate_count} duplicate timestamps found."
    )

    result = (
        result
        .drop_duplicates("timestamp")
        .reset_index(drop=True)
    )


# ============================================================
# QUALITY
# ============================================================

missing_rate = float(
    result["residual_load_forecast"].isna().mean()
)

negative_count = int(
    (
        result["residual_load_forecast"]
        .dropna()
        < 0
    ).sum()
)


print("\n----------------------------------------------")
print("CONVERSION RESULT")
print("----------------------------------------------")

print(
    f"Rows              : {len(result):,}"
)

print(
    f"Start              : {result['timestamp'].min()}"
)

print(
    f"End                : {result['timestamp'].max()}"
)

print(
    f"Missing rate       : {missing_rate:.4%}"
)

print(
    f"Negative values    : {negative_count}"
)

print(
    f"Duplicates removed : {duplicate_count}"
)

print("\nFirst 5 rows:")
print(result.head())


# ============================================================
# SAVE
# ============================================================

result.to_csv(
    OUTPUT,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# REPORT
# ============================================================

report = {

    "source":
        "Bundesnetzagentur | SMARD.de",

    "series":
        "Forecasted residual load",

    "definition":
        "Forecasted electricity consumption minus "
        "forecasted PV and wind generation",

    "rows": int(len(result)),

    "missing_rate": missing_rate,

    "negative_values": negative_count,

    "duplicates_removed": duplicate_count,

    "start":
        str(result["timestamp"].min()),

    "end":
        str(result["timestamp"].max()),

    "output_file":
        str(OUTPUT),
}


with open(
    REPORT,
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
print(" CONVERSION COMPLETE")
print("==============================================")

print(f"\nSaved:\n{OUTPUT}")
print(f"\nReport:\n{REPORT}")

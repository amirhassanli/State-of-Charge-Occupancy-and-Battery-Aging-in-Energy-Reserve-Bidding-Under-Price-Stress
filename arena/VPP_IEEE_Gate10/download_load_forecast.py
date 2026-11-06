from pathlib import Path
import io
import json
import pandas as pd
import requests


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

RAW = ROOT / "data" / "raw" / "smard"
RAW.mkdir(parents=True, exist_ok=True)

OUTPUT = RAW / "load_forecast.csv"
REPORT = RAW / "load_forecast_download_report.json"


# ============================================================
# SMARD DOWNLOAD
# ============================================================

URL = (
    "https://www.smard.de/"
    "nip-download-manager/"
    "nip/download/market-data"
)


START = pd.Timestamp(
    "2024-01-01",
    tz="Europe/Berlin"
)

END = (
    pd.Timestamp(
        "2025-09-30",
        tz="Europe/Berlin"
    )
    + pd.Timedelta(days=1)
    - pd.Timedelta(milliseconds=1)
)


timestamp_from = int(
    START.tz_convert("UTC").timestamp() * 1000
)

timestamp_to = int(
    END.tz_convert("UTC").timestamp() * 1000
)


# ============================================================
# VERIFIED SMARD MODULE
# ============================================================
#
# 6000411 = Actual grid load
# 6004362 = Forecasted grid load
#
# The previous attempt used 6000411 incorrectly.
# ============================================================

MODULE_ID = 6004362


payload = {
    "request_form": [
        {
            "format": "CSV",
            "moduleIds": [MODULE_ID],
            "region": "DE",
            "timestamp_from": timestamp_from,
            "timestamp_to": timestamp_to,
            "type": "discrete",
            "language": "en",
        }
    ]
}


# ============================================================
# START
# ============================================================

print()
print("==============================================")
print(" SMARD FORECASTED LOAD DOWNLOAD")
print("==============================================")
print()

print(f"Period : {START} → {END}")
print(f"Module : {MODULE_ID}")
print(f"URL    : {URL}")
print()


# ============================================================
# REQUEST
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "AlocaBid-IEEE-Research/1.0"
})


response = session.post(
    URL,
    json=payload,
    timeout=120
)


print(
    f"HTTP status: {response.status_code}"
)

response.raise_for_status()


# ============================================================
# SAVE RAW RESPONSE
# ============================================================

raw_file = (
    RAW /
    "load_forecast_raw_response.bin"
)

with open(raw_file, "wb") as f:
    f.write(response.content)

print()
print(f"Raw response saved:")
print(raw_file)


# ============================================================
# READ SMARD CSV
# ============================================================
#
# SMARD exports are semicolon-separated.
# ============================================================

try:

    df = pd.read_csv(
        io.BytesIO(response.content),
        sep=";",
        engine="python"
    )

except Exception as exc:

    print()
    print("Could not parse SMARD CSV.")
    print(response.text[:1000])

    raise RuntimeError(
        "SMARD response could not be parsed."
    ) from exc


# ============================================================
# DISPLAY STRUCTURE
# ============================================================

print()
print("----------------------------------------------")
print("DOWNLOADED DATA STRUCTURE")
print("----------------------------------------------")

print("Columns:")

for col in df.columns:
    print(f"  - {col}")

print()
print(f"Rows returned: {len(df):,}")

print()
print("First 5 rows:")
print(df.head())


# ============================================================
# EXPECTED COLUMNS
# ============================================================

# Expected SMARD export:
#
# Start date
# End date
# grid load [MWh]
# Original resolutions
#
# The exact naming can vary slightly, so detect by name.

start_candidates = [
    c for c in df.columns
    if "Start date" in str(c)
]

end_candidates = [
    c for c in df.columns
    if "End date" in str(c)
]

value_candidates = [
    c for c in df.columns
    if "grid load" in str(c).lower()
]


if not start_candidates:

    raise ValueError(
        "Could not find 'Start date' column."
    )


if not end_candidates:

    raise ValueError(
        "Could not find 'End date' column."
    )


if not value_candidates:

    raise ValueError(
        "Could not find forecast grid-load column."
    )


start_col = start_candidates[0]
end_col = end_candidates[0]
value_col = value_candidates[0]


print()
print("----------------------------------------------")
print("COLUMN MAPPING")
print("----------------------------------------------")

print(f"Start time : {start_col}")
print(f"End time   : {end_col}")
print(f"Value      : {value_col}")


# ============================================================
# PARSE TIMESTAMPS
# ============================================================

df["timestamp"] = pd.to_datetime(
    df[start_col],
    errors="coerce",
    utc=True
)


if df["timestamp"].isna().any():

    bad = int(
        df["timestamp"].isna().sum()
    )

    raise ValueError(
        f"{bad} invalid start timestamps found."
    )


df["timestamp"] = (
    df["timestamp"]
    .dt.tz_convert("Europe/Berlin")
)


# ============================================================
# PARSE VALUES
# ============================================================

df["load_forecast"] = pd.to_numeric(
    df[value_col],
    errors="coerce"
)


# ============================================================
# SELECT STANDARDIZED DATA
# ============================================================

result = df[
    [
        "timestamp",
        "load_forecast"
    ]
].copy()


# ============================================================
# FILTER PERIOD
# ============================================================

result = result[
    (result["timestamp"] >= START)
    &
    (result["timestamp"] <= END)
].copy()


# ============================================================
# SORT + DUPLICATE CHECK
# ============================================================

result = (
    result
    .sort_values("timestamp")
    .reset_index(drop=True)
)


duplicates = int(
    result["timestamp"].duplicated().sum()
)


if duplicates > 0:

    print(
        f"[WARNING] {duplicates} duplicate timestamps."
    )

    result = (
        result
        .drop_duplicates("timestamp")
        .reset_index(drop=True)
    )


# ============================================================
# SAVE
# ============================================================

result.to_csv(
    OUTPUT,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# QUALITY REPORT
# ============================================================

missing_rate = float(
    result["load_forecast"].isna().mean()
)

negative_count = int(
    (
        result["load_forecast"]
        .dropna()
        < 0
    ).sum()
)


report = {

    "gate": "10B.1",

    "module_id": MODULE_ID,

    "description":
        "SMARD Forecasted Electricity Consumption / Grid Load",

    "period": {
        "start": str(START),
        "end": str(END),
    },

    "rows": int(len(result)),

    "duplicates_after_cleaning": int(
        result["timestamp"].duplicated().sum()
    ),

    "missing_rate": missing_rate,

    "negative_values": negative_count,

    "start_timestamp": (
        str(result["timestamp"].min())
        if len(result)
        else None
    ),

    "end_timestamp": (
        str(result["timestamp"].max())
        if len(result)
        else None
    ),

    "output_file": str(OUTPUT),

    "source":
        "Bundesnetzagentur | SMARD.de",
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


# ============================================================
# FINAL OUTPUT
# ============================================================

print()
print("==============================================")
print(" LOAD FORECAST DOWNLOAD COMPLETE")
print("==============================================")

print()
print(f"Rows       : {len(result):,}")
print(
    f"Start      : {result['timestamp'].min()}"
)
print(
    f"End        : {result['timestamp'].max()}"
)
print(
    f"Missing    : {missing_rate:.4%}"
)
print(
    f"Duplicates : {duplicates}"
)
print(
    f"Negative   : {negative_count}"
)

print()
print("Saved:")
print(OUTPUT)

print()
print("Report:")
print(REPORT)

print()
print("[SUCCESS] Verified forecasted-load module downloaded.")

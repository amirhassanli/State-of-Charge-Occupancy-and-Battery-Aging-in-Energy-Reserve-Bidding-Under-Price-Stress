#!/usr/bin/env python3
"""Download hourly SMARD electricity data and merge it into one CSV.

Date range: 2021-01-01 through 2026-08-31 inclusive, Europe/Berlin.
Output: SMARD_data_2021_2026.csv

Install: pip install pandas requests

SMARD filter IDs (verified against the published SMARD API documentation):
  4169 = day-ahead market price Germany/Luxembourg (DE-LU)
   410 = total grid load (Netzlast)
  4068 = photovoltaic generation (PV)  [NOT 4066]
  4067 = wind onshore generation
  1225 = wind offshore generation

SMARD's public chart endpoint exposes data in timestamped chunks. Values are
reported with Unix timestamps in milliseconds (UTC); the resulting timestamp
column is converted to Europe/Berlin and retains the UTC offset, so the two
occurrences of a repeated autumn DST hour remain distinguishable.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.smard.de/app/chart_data"
START_LOCAL = pd.Timestamp("2021-01-01 00:00:00", tz="Europe/Berlin")
END_LOCAL_EXCLUSIVE = pd.Timestamp("2026-09-01 00:00:00", tz="Europe/Berlin")
OUTPUT_FILE = Path("SMARD_data_2021_2026.csv")

SERIES = {
    "DA_price_EUR_per_MWh": {"filter": 4169, "preferred_region": "DE-LU"},
    "Grid_load_MW": {"filter": 410, "preferred_region": "DE"},
    "PV_generation_MW": {"filter": 4068, "preferred_region": "DE"},
    "Wind_onshore_MW": {"filter": 4067, "preferred_region": "DE"},
    "Wind_offshore_MW": {"filter": 1225, "preferred_region": "DE"},
}


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "SMARD-research-data-downloader/1.0 (academic research)",
        "Accept": "application/json,text/plain,*/*",
    })
    return session


def get_json(session: requests.Session, url: str) -> dict:
    response = session.get(url, timeout=(15, 90))
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Unexpected JSON structure from {url}")
    return payload


def fetch_series_for_region(
    session: requests.Session, filter_id: int, region: str,
    start_utc_ms: int, end_utc_ms: int,
) -> pd.Series:
    """Fetch all chunks intersecting the requested period for one filter/region."""
    index_url = f"{BASE_URL}/{filter_id}/{region}/index_hour.json"
    index_payload = get_json(session, index_url)
    available = index_payload.get("timestamps", [])
    if not available:
        raise RuntimeError(f"No hourly timestamps listed for filter={filter_id}, region={region}")

    # SMARD chunks are approximately weekly. Include a safety margin before the
    # start so the chunk containing the first requested hour is not missed.
    # Also include the first chunk timestamp at/after the exclusive end only if
    # needed; exact filtering below removes all out-of-range observations.
    chunk_stamps = sorted({int(x) for x in available
                           if start_utc_ms - 8 * 24 * 60 * 60 * 1000 <= int(x) <= end_utc_ms})
    if not chunk_stamps:
        raise RuntimeError(
            f"No SMARD chunks intersect requested range for filter={filter_id}, region={region}"
        )

    points: list[tuple[int, float]] = []
    for i, chunk_ts in enumerate(chunk_stamps, start=1):
        url = f"{BASE_URL}/{filter_id}/{region}/{filter_id}_{region}_hour_{chunk_ts}.json"
        try:
            payload = get_json(session, url)
        except requests.HTTPError as exc:
            # A stale index entry or a temporarily unavailable chunk should not
            # silently pass; report the exact URL and stop this region attempt.
            raise RuntimeError(f"Failed to download SMARD chunk: {url} ({exc})") from exc
        for row in payload.get("series", []):
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            ts, value = row[0], row[1]
            if ts is None or value is None:
                continue
            ts_i = int(ts)
            if start_utc_ms <= ts_i < end_utc_ms:
                try:
                    val_f = float(value)
                except (TypeError, ValueError):
                    continue
                points.append((ts_i, val_f))
        print(f"    filter {filter_id} / {region}: chunk {i}/{len(chunk_stamps)}", flush=True)
        # Small pause to avoid sending requests too aggressively.
        time.sleep(0.05)

    if not points:
        raise RuntimeError(f"Downloaded no in-range observations for filter={filter_id}, region={region}")

    df = pd.DataFrame(points, columns=["timestamp_ms", "value"])
    # If the API returns duplicated timestamps across adjacent chunks, retain
    # the last downloaded observation for that timestamp.
    df = df.drop_duplicates(subset="timestamp_ms", keep="last").sort_values("timestamp_ms")
    idx = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True).dt.tz_convert("Europe/Berlin")
    result = pd.Series(df["value"].to_numpy(), index=pd.DatetimeIndex(idx, name="timestamp_berlin"))
    result = result[~result.index.duplicated(keep="last")].sort_index()
    return result


def fetch_series(session: requests.Session, filter_id: int, preferred_region: str) -> tuple[pd.Series, str]:
    """Try the intended region first, with a transparent DE fallback if needed."""
    start_utc_ms = int(START_LOCAL.tz_convert("UTC").timestamp() * 1000)
    end_utc_ms = int(END_LOCAL_EXCLUSIVE.tz_convert("UTC").timestamp() * 1000)
    regions: Iterable[str] = [preferred_region]
    if preferred_region != "DE":
        regions = [preferred_region, "DE"]
    errors = []
    for region in regions:
        try:
            s = fetch_series_for_region(session, filter_id, region, start_utc_ms, end_utc_ms)
            return s, region
        except Exception as exc:
            errors.append(f"{region}: {exc}")
            print(f"  Warning: filter {filter_id} unavailable in region {region}: {exc}", file=sys.stderr)
    raise RuntimeError(f"Could not fetch filter={filter_id}. Attempts: {' | '.join(errors)}")


def main() -> None:
    session = make_session()
    downloaded: dict[str, pd.Series] = {}
    source_regions: dict[str, str] = {}

    print("Downloading hourly SMARD data from 2021-01-01 to 2026-08-31 ...")
    for column, spec in SERIES.items():
        print(f"\n[{column}] filter={spec['filter']}, preferred region={spec['preferred_region']}")
        series, actual_region = fetch_series(session, spec["filter"], spec["preferred_region"])
        downloaded[column] = series.rename(column)
        source_regions[column] = actual_region
        print(f"  Received {len(series):,} observations (region={actual_region}).")

    # Union-join on timezone-aware hourly instants. A missing value is left NaN;
    # the script deliberately does not interpolate or fabricate observations.
    merged = pd.concat(downloaded.values(), axis=1).sort_index()
    merged["Wind_generation_MW"] = merged["Wind_onshore_MW"] + merged["Wind_offshore_MW"]
    merged = merged[[
        "DA_price_EUR_per_MWh",
        "Grid_load_MW",
        "PV_generation_MW",
        "Wind_onshore_MW",
        "Wind_offshore_MW",
        "Wind_generation_MW",
    ]]

    # Build the expected sequence in UTC, then render in Berlin local time.
    # This correctly gives 23/25 local hours on DST transition days and avoids
    # manufacturing a non-existent or merging two distinct local hours.
    expected_utc = pd.date_range(
        START_LOCAL.tz_convert("UTC"),
        END_LOCAL_EXCLUSIVE.tz_convert("UTC"),
        freq="h", inclusive="left",
    )
    expected_berlin = expected_utc.tz_convert("Europe/Berlin")
    merged = merged.reindex(expected_berlin)
    merged.index.name = "timestamp_berlin"

    # Add the source UTC timestamp for unambiguous joins/reproducibility. The
    # Berlin timestamp remains the primary timestamp requested by the user.
    out = merged.copy()
    out.insert(0, "timestamp_utc", out.index.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"))
    out.insert(0, "timestamp_berlin", out.index.strftime("%Y-%m-%dT%H:%M:%S%z"))
    out = out.reset_index(drop=True)
    out.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig", float_format="%.6f")

    print("\nFinished.")
    print(f"CSV: {OUTPUT_FILE.resolve()}")
    print(f"Rows (expected hourly instants): {len(out):,}")
    print(f"Date range: {out['timestamp_berlin'].iloc[0]} to {out['timestamp_berlin'].iloc[-1]}")
    print("Source regions used:")
    for name, region in source_regions.items():
        print(f"  {name}: {region}")
    print("Missing values by column (not interpolated):")
    print(out.drop(columns=["timestamp_berlin", "timestamp_utc"]).isna().sum().to_string())
    print("\nNote: inspect source-region choices and missing values before using the data in a paper.")


if __name__ == "__main__":
    main()

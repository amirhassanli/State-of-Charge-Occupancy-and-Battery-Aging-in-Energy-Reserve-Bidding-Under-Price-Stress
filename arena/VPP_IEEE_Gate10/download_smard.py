from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


BASE = "https://www.smard.de/app/chart_data"

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw" / "smard"
RAW.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "AlocaBid-IEEE-Research/1.0"
})


FILTERS = {
    "da_price": {
        "filter": 4169,
        "region": "DE-LU",
        "resolution": "hour",
    },
    "load_actual": {
        "filter": 410,
        "region": "DE",
        "resolution": "quarterhour",
    },
    "wind_on_actual": {
        "filter": 4067,
        "region": "DE",
        "resolution": "quarterhour",
    },
    "wind_off_actual": {
        "filter": 1225,
        "region": "DE",
        "resolution": "quarterhour",
    },
    "pv_actual": {
        "filter": 4068,
        "region": "DE",
        "resolution": "quarterhour",
    },
    "residual_load_actual": {
        "filter": 4359,
        "region": "DE",
        "resolution": "quarterhour",
    },
    "wind_on_forecast": {
        "filter": 123,
        "region": "DE",
        "resolution": "quarterhour",
    },
    "wind_off_forecast": {
        "filter": 3791,
        "region": "DE",
        "resolution": "quarterhour",
    },
    "pv_forecast": {
        "filter": 125,
        "region": "DE",
        "resolution": "quarterhour",
    },
}


def get_json(url: str, retries: int = 5) -> dict:
    last_error = None

    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last_error = exc
            time.sleep(2 ** attempt)

    raise RuntimeError(f"Failed after {retries} attempts: {url}") from last_error


def get_timestamps(filter_id: int, region: str, resolution: str) -> list[int]:
    url = f"{BASE}/{filter_id}/{region}/index_{resolution}.json"
    payload = get_json(url)
    return payload.get("timestamps", [])


def fetch_series(
    name: str,
    filter_id: int,
    region: str,
    resolution: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:

    start = pd.Timestamp(start_date, tz="Europe/Berlin")
    end = pd.Timestamp(end_date, tz="Europe/Berlin") + pd.Timedelta(days=1)

    timestamps = get_timestamps(filter_id, region, resolution)

    if not timestamps:
        raise RuntimeError(f"No timestamps available for {name}")

    frames = []

    for ts in timestamps:

        url = (
            f"{BASE}/{filter_id}/{region}/"
            f"{filter_id}_{region}_{resolution}_{ts}.json"
        )

        try:
            payload = get_json(url)
        except Exception as exc:
            print(f"[WARNING] failed bucket {ts}: {exc}")
            continue

        series = payload.get("series", [])

        rows = []

        for item in series:

            if isinstance(item, list) and len(item) >= 2:
                timestamp_ms, value = item[0], item[1]

                rows.append(
                    {
                        "timestamp": pd.to_datetime(
                            timestamp_ms, unit="ms", utc=True
                        ),
                        name: value,
                    }
                )

            elif isinstance(item, dict):
                # compatibility with newer TimeSeries2 format
                timestamp_ms = item.get("timestamp")
                versions = item.get("versions", [])

                if timestamp_ms is None:
                    continue

                value = None
                if versions:
                    value = versions[0].get("value")

                rows.append(
                    {
                        "timestamp": pd.to_datetime(
                            timestamp_ms, unit="ms", utc=True
                        ),
                        name: value,
                    }
                )

        if rows:
            df = pd.DataFrame(rows)

            df["timestamp"] = (
                df["timestamp"]
                .dt.tz_convert("Europe/Berlin")
            )

            df = df[
                (df["timestamp"] >= start)
                & (df["timestamp"] < end)
            ]

            if not df.empty:
                frames.append(df)

    if not frames:
        raise RuntimeError(f"No observations collected for {name}")

    result = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates("timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    result.to_csv(
        RAW / f"{name}.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"[OK] {name}: "
        f"{len(result):,} rows | "
        f"{result['timestamp'].min()} → "
        f"{result['timestamp'].max()}"
    )

    return result


def main():

    start_date = "2024-01-01"
    end_date = "2025-09-30"

    manifest = []

    for name, cfg in FILTERS.items():

        print(f"\nDownloading {name} ...")

        df = fetch_series(
            name=name,
            filter_id=cfg["filter"],
            region=cfg["region"],
            resolution=cfg["resolution"],
            start_date=start_date,
            end_date=end_date,
        )

        manifest.append({
            "name": name,
            "filter": cfg["filter"],
            "region": cfg["region"],
            "resolution": cfg["resolution"],
            "rows": len(df),
            "start": str(df["timestamp"].min()),
            "end": str(df["timestamp"].max()),
        })

    pd.DataFrame(manifest).to_csv(
        RAW / "smard_manifest.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("\n===================================")
    print("GATE 10A DOWNLOAD COMPLETE")
    print("===================================")


if __name__ == "__main__":
    main()
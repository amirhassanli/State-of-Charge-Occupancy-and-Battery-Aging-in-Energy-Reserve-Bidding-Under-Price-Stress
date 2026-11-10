"""Download and normalize public German electricity time series.

The raw API responses are archived unchanged. The processed panel is a derived
hourly dataset for the manuscript's daily model; no battery telemetry is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

API = "https://api.energy-charts.info"
BERLIN = ZoneInfo("Europe/Berlin")


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "agingbid-reproducibility/1.0"})
    try:
        with urlopen(request, timeout=120) as response:
            return response.read()
    except HTTPError as exc:
        retry_after = exc.headers.get("Retry-After")
        suffix = f" Retry-After={retry_after}s; rerun after that interval." if retry_after else ""
        raise RuntimeError(f"API request failed with HTTP {exc.code}: {url}.{suffix}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not retrieve {url}: {exc.reason}") from exc


def get_url(endpoint: str, **params: str) -> str:
    return f"{API}/{endpoint}?{urlencode(params)}"


def hourly_series(timestamps: list[int], values: list[float | None], name: str) -> pd.Series:
    if len(timestamps) != len(values):
        raise ValueError(f"{name}: {len(timestamps)} timestamps but {len(values)} values")
    index = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(BERLIN)
    series = pd.Series(pd.to_numeric(values, errors="coerce"), index=index, name=name)
    if series.index.has_duplicates:
        raise ValueError(f"{name}: duplicate API timestamps")
    return series.resample("1h").mean()


def save_raw(path: Path, payload: bytes) -> tuple[dict, str]:
    path.write_bytes(payload)
    return json.loads(payload), hashlib.sha256(payload).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2025-12-01", help="First local date, inclusive")
    parser.add_argument("--end", default="2026-08-21", help="Last local date requested from the API")
    parser.add_argument("--end-hour", type=int, default=7,
                        help="Keep data through this local hour on --end (manuscript cutoff: 7)")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()
    if not 0 <= args.end_hour <= 23:
        parser.error("--end-hour must be in 0..23")

    raw_dir = args.data_dir / "raw" / "energy_charts"
    processed_dir = args.data_dir / "processed"
    metadata_dir = args.data_dir / "metadata"
    for directory in (raw_dir, processed_dir, metadata_dir):
        directory.mkdir(parents=True, exist_ok=True)

    stamp = f"{args.start}_{args.end}"
    urls = {
        "price": get_url("price", bzn="DE-LU", start=args.start, end=args.end),
        "public_power": get_url("public_power", country="de", start=args.start, end=args.end),
    }
    raw_payloads = {name: fetch(url) for name, url in urls.items()}
    price, price_hash = save_raw(raw_dir / f"price_DE-LU_{stamp}.json", raw_payloads["price"])
    power, power_hash = save_raw(raw_dir / f"public_power_DE_{stamp}.json", raw_payloads["public_power"])

    if "price" not in price or "unix_seconds" not in price:
        raise ValueError(f"Unexpected price response fields: {list(price)}")
    price_series = hourly_series(price["unix_seconds"], price["price"], "da_price")
    named_series = {item["name"].casefold(): item["data"] for item in power.get("production_types", [])}
    required = ("load", "solar", "wind onshore", "wind offshore")
    missing = [name for name in required if name not in named_series]
    if missing:
        raise ValueError(f"Missing required public-power series {missing}; got {sorted(named_series)}")

    power_index = power.get("unix_seconds", [])
    series = [
        price_series,
        hourly_series(power_index, named_series["load"], "load_raw_mw"),
        hourly_series(power_index, named_series["solar"], "solar_raw_mw"),
        hourly_series(power_index, named_series["wind onshore"], "wind_onshore_raw_mw"),
        hourly_series(power_index, named_series["wind offshore"], "wind_offshore_raw_mw"),
    ]
    hourly = pd.concat(series, axis=1).sort_index()
    hourly["wind_raw_mw"] = hourly["wind_onshore_raw_mw"] + hourly["wind_offshore_raw_mw"]
    cutoff = pd.Timestamp(f"{args.end} {args.end_hour:02d}:00", tz=BERLIN)
    hourly = hourly.loc[(hourly.index >= pd.Timestamp(args.start, tz=BERLIN)) & (hourly.index <= cutoff)]

    usable = hourly.dropna(subset=["da_price", "load_raw_mw", "solar_raw_mw", "wind_raw_mw"]).copy()
    if usable.empty:
        raise ValueError("No complete hourly observations were returned for the requested period")
    load_q95 = float(np.nanpercentile(usable["load_raw_mw"], 95))
    solar_max = float(usable["solar_raw_mw"].max())
    wind_max = float(usable["wind_raw_mw"].max())
    if min(load_q95, solar_max, wind_max) <= 0:
        raise ValueError("Cannot compute positive load/PV/wind scaling factors")
    factors = {"load": 5.0 / load_q95, "solar": 4.0 / solar_max, "wind": 2.0 / wind_max}
    usable["load"] = usable["load_raw_mw"] * factors["load"]
    usable["pv"] = usable["solar_raw_mw"] * factors["solar"]
    usable["wind"] = usable["wind_raw_mw"] * factors["wind"]
    usable.index.name = "timestamp"
    processed_panel = processed_dir / f"hourly_vpp_panel_{stamp}.csv"
    usable.reset_index().to_csv(processed_panel, index=False)

    complete_days = int((usable.groupby(usable.index.date).size() == 24).sum())
    retrieved = datetime.now(timezone.utc).isoformat()
    manifest = {
        "retrieved_at_utc": retrieved,
        "requested_local_start": args.start,
        "requested_local_end": args.end,
        "processed_local_cutoff": cutoff.isoformat(),
        "timezone": "Europe/Berlin",
        "sources": {
            "day_ahead_price": {"url": urls["price"], "publisher": "Energy-Charts API; source: Bundesnetzagentur | SMARD.de", "license": price.get("license_info"), "unit": price.get("unit"), "sha256": price_hash},
            "public_power": {"url": urls["public_power"], "publisher": "Fraunhofer ISE Energy-Charts", "license": "CC BY 4.0; attribution required", "series": list(named_series), "units": "MW", "sha256": power_hash},
        },
        "processing": {
            "raw_resolution": "API interval series; resampled to local-clock hourly means",
            "wind": "onshore plus offshore generation",
            "scaling_factors": factors,
            "mapping": "load q95 -> 5 MW; study-window solar maximum -> 4 MW; combined wind maximum -> 2 MW",
            "missing_values": "rows missing any required series are excluded from the processed panel; raw responses are retained",
            "complete_24h_days": complete_days,
            "usable_hourly_rows": int(len(usable)),
        },
        "processed_panel": {
            "path": str(processed_panel.relative_to(args.data_dir)),
            "sha256": hashlib.sha256(processed_panel.read_bytes()).hexdigest(),
            "rows": int(len(usable)),
        },
        "battery_telemetry": None,
    }
    manifest_path = metadata_dir / f"manifest_{stamp}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Raw responses: {raw_dir}")
    print(f"Processed panel: {processed_panel}")
    print(f"Manifest: {manifest_path}")
    print(f"Rows={len(usable)}, complete 24-hour days={complete_days}, scaling={factors}")


if __name__ == "__main__":
    main()

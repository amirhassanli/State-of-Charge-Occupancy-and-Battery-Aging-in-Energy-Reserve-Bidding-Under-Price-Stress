
from pathlib import Path
from datetime import datetime
import re
import pandas as pd
from playwright.sync_api import sync_playwright

ROOT = Path("germany_balancing_data")
RAW = ROOT / "raw"
REPORTS = ROOT / "reports"

RAW.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

SOURCES = {
    "rebap": (
        "https://www.netztransparenz.de/"
        "Regelenergie/Ausgleichsenergiepreis/reBAP"
    ),
    "afrr": "https://www.regelleistung.net/apps/datacenter/",
}

def safe_name(text):
    text = re.sub(r"[^\w.-]+", "_", text)
    return text.strip("._")[:100] or "download"

def inspect_file(path):
    """Read CSV/XLSX without inventing or imputing data."""
    try:
        if path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        elif path.suffix.lower() in (".csv", ".txt"):
            # Try common encodings and separators.
            df = None
            for encoding in ("utf-8-sig", "cp1252", "latin1"):
                for sep in (None, ";", ",", "\t"):
                    try:
                        candidate = pd.read_csv(
                            path, encoding=encoding, sep=sep,
                            engine="python"
                        )
                        if len(candidate.columns) > 1:
                            df = candidate
                            break
                    except Exception:
                        pass
                if df is not None:
                    break
            if df is None:
                raise ValueError("Could not parse CSV")
        else:
            return None

        df.columns = [
            re.sub(r"\s+", " ", str(c)).strip()
            for c in df.columns
        ]

        # Preserve original values. Only identify likely time columns.
        time_candidates = [
            c for c in df.columns
            if any(k in c.lower() for k in (
                "timestamp", "date", "time", "datum", "zeit",
                "delivery", "begin", "start", "period"
            ))
        ]

        metadata = {
            "file": str(path),
            "rows": len(df),
            "columns": list(df.columns),
            "likely_time_columns": time_candidates,
            "missing_cells": int(df.isna().sum().sum()),
        }

        # Save a normalized copy without dropping source columns.
        out = REPORTS / f"{path.stem}_normalized.csv"
        df.to_csv(out, index=False, encoding="utf-8-sig")
        return metadata

    except Exception as exc:
        return {
            "file": str(path),
            "error": str(exc)
        }

def main():
    print("Official source downloader")
    print("Files will be saved under:", ROOT.resolve())
    print()
    print("In each browser tab:")
    print("1. Select the delivery-date range.")
    print("2. Select the required market/product.")
    print("3. Click the site's official CSV/Excel download.")
    print("4. Return to this terminal when finished.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(accept_downloads=True)

        for category, url in SOURCES.items():
            page = context.new_page()

            def save_download(download, cat=category):
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                original = Path(download.suggested_filename)
                filename = safe_name(original.stem)
                suffix = original.suffix or ".bin"
                target = RAW / f"{cat}_{stamp}_{filename}{suffix}"
                download.save_as(str(target))
                print(f"\nSaved [{cat}]: {target}")

            page.on("download", save_download)

            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )
                print(f"\nOpened {category.upper()}: {url}")
            except Exception as exc:
                print(f"Could not fully load {url}: {exc}")

        input(
            "\nDownload the required files in the opened tabs. "
            "When finished, return here and press Enter..."
        )

        browser.close()

    # Inspect every downloaded data file.
    records = []
    for path in sorted(RAW.iterdir()):
        if path.is_file():
            result = inspect_file(path)
            if result is not None:
                records.append(result)

    report = pd.DataFrame(records)
    report_path = REPORTS / "download_inventory.csv"
    report.to_csv(report_path, index=False, encoding="utf-8-sig")

    print("\nFinished.")
    print("Raw downloads:", RAW.resolve())
    print("Inventory:", report_path.resolve())
    print("Normalized copies:", REPORTS.resolve())
    print(
        "\nIMPORTANT: normalized copies preserve source columns; "
        "they are not yet certified as model-ready datasets."
    )

if __name__ == "__main__":
    main()

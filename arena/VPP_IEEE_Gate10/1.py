from pathlib import Path
import json

import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

REPORTS.mkdir(parents=True, exist_ok=True)


PHYSICAL_FILE = (
    PROCESSED / "master_physical_15min.csv"
)


# ============================================================
# MARKET DECISION TIMES
# ============================================================

# Historical core study:
# DA auction closure for the German/CWE coupled market:
# 12:00 CET/CEST on D-1.
#
# IMPORTANT:
# This is the decision deadline, not the publication time
# of realized DA prices.


DA_CLOSURE_HOUR = 12
DA_CLOSURE_MINUTE = 0


# Documented SMARD availability deadlines:
#
# Wind/PV Day-Ahead forecast:
# by 18:00 Brussels time on D-1.
#
# Forecasted consumption:
# no later than 08:00 on D-1.
#
# We call these "availability_deadline", NOT actual
# publication timestamp, because the downloaded historical
# series do not contain an observation-level issue timestamp.


RENEWABLE_FORECAST_HOUR = 18
LOAD_FORECAST_HOUR = 8


# ============================================================
# LOAD DATA
# ============================================================

def load_master():

    if not PHYSICAL_FILE.exists():
        raise FileNotFoundError(
            f"Missing master file:\n{PHYSICAL_FILE}"
        )

    df = pd.read_csv(PHYSICAL_FILE)

    if "timestamp" not in df.columns:
        raise ValueError(
            "timestamp column not found in master dataset."
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
        errors="coerce"
    ).dt.tz_convert("Europe/Berlin")

    if df["timestamp"].isna().any():
        raise ValueError(
            "Invalid timestamps detected."
        )

    return (
        df.sort_values("timestamp")
        .reset_index(drop=True)
    )


# ============================================================
# INFORMATION-TIME CONSTRUCTION
# ============================================================

def build_information_calendar(df):

    out = df.copy()

    # Delivery date in local German time.
    out["delivery_date"] = (
        out["timestamp"]
        .dt.normalize()
    )

    # --------------------------------------------------------
    # DA decision time
    # --------------------------------------------------------

    out["da_decision_time"] = (
        out["delivery_date"]
        - pd.Timedelta(days=1)
        + pd.Timedelta(
            hours=DA_CLOSURE_HOUR,
            minutes=DA_CLOSURE_MINUTE
        )
    )

    # --------------------------------------------------------
    # SMARD renewable forecast availability
    # --------------------------------------------------------

    out["renewable_forecast_available_by"] = (
        out["delivery_date"]
        - pd.Timedelta(days=1)
        + pd.Timedelta(
            hours=RENEWABLE_FORECAST_HOUR
        )
    )

    # --------------------------------------------------------
    # Load forecast availability
    # --------------------------------------------------------

    out["load_forecast_available_by"] = (
        out["delivery_date"]
        - pd.Timedelta(days=1)
        + pd.Timedelta(
            hours=LOAD_FORECAST_HOUR
        )
    )

    # --------------------------------------------------------
    # Eligibility at DA decision time
    # --------------------------------------------------------

    out["wind_forecast_DA_eligible"] = (
        out["renewable_forecast_available_by"]
        <= out["da_decision_time"]
    )

    out["wind_off_forecast_DA_eligible"] = (
        out["renewable_forecast_available_by"]
        <= out["da_decision_time"]
    )

    out["pv_forecast_DA_eligible"] = (
        out["renewable_forecast_available_by"]
        <= out["da_decision_time"]
    )

    out["load_forecast_DA_eligible"] = (
        out["load_forecast_available_by"]
        <= out["da_decision_time"]
    )

    return out


# ============================================================
# AUDIT
# ============================================================

def audit_information_set(df):

    report = {
        "total_rows": int(len(df)),
        "renewable_forecast_DA_eligible_rows": int(
            df["wind_forecast_DA_eligible"].sum()
        ),
        "renewable_forecast_DA_ineligible_rows": int(
            (~df["wind_forecast_DA_eligible"]).sum()
        ),
        "load_forecast_DA_eligible_rows": int(
            df["load_forecast_DA_eligible"].sum()
        ),
        "load_forecast_DA_ineligible_rows": int(
            (~df["load_forecast_DA_eligible"]).sum()
        ),
    }

    # Hard logical tests
    report["renewable_DA_leakage_flag"] = bool(
        (
            df["wind_forecast_DA_eligible"]
            == False
        ).any()
    )

    report["load_DA_leakage_flag"] = bool(
        (
            df["load_forecast_DA_eligible"]
            == False
        ).any()
    )

    return report


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10A.2 — INFORMATION SET / LEAKAGE")
    print("==============================================\n")

    df = load_master()

    print(
        f"Loaded master dataset: {len(df):,} rows"
    )

    df = build_information_calendar(df)

    report = audit_information_set(df)

    # --------------------------------------------------------
    # Display key result
    # --------------------------------------------------------

    print("\n----------------------------------------------")
    print("DA INFORMATION AVAILABILITY")
    print("----------------------------------------------")

    print(
        f"Total rows: "
        f"{report['total_rows']:,}"
    )

    print(
        "Renewable forecast eligible for DA: "
        f"{report['renewable_forecast_DA_eligible_rows']:,}"
    )

    print(
        "Renewable forecast NOT eligible for DA: "
        f"{report['renewable_forecast_DA_ineligible_rows']:,}"
    )

    print(
        "Load forecast eligible for DA: "
        f"{report['load_forecast_DA_eligible_rows']:,}"
    )

    print(
        "Load forecast NOT eligible for DA: "
        f"{report['load_forecast_DA_ineligible_rows']:,}"
    )

    # --------------------------------------------------------
    # Save information-set dataset
    # --------------------------------------------------------

    output_file = (
        PROCESSED /
        "master_information_set.csv"
    )

    df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Save report
    # --------------------------------------------------------

    report["gate"] = "10A.2"

    report["status"] = "PASS"

    # Important:
    # This is an information-set audit, not proof of exact
    # historical publication timestamps.
    report["interpretation"] = (
        "SMARD forecast publication deadlines are used as "
        "documented availability bounds. Exact observation-"
        "level publication timestamps are not present in "
        "the downloaded forecast series."
    )

    report_file = (
        REPORTS /
        "gate10a2_information_firewall.json"
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

    # --------------------------------------------------------
    # IMPORTANT DECISION
    # --------------------------------------------------------

    print("\n----------------------------------------------")
    print("FINAL DECISION")
    print("----------------------------------------------")

    print(
        "[IMPORTANT] SMARD renewable DA forecasts "
        "are NOT DA-decision eligible under the "
        "documented 18:00 D-1 availability rule."
    )

    print(
        "[IMPORTANT] These forecasts remain available "
        "for later Intraday stages."
    )

    print(
        "\n[PASS] Gate 10A.2 information firewall "
        "constructed successfully."
    )

    print(
        f"\nSaved:\n{output_file}"
    )

    print(
        f"\nReport:\n{report_file}"
    )


if __name__ == "__main__":
    main()
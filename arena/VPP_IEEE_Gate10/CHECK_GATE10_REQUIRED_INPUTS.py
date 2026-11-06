from pathlib import Path
import sys

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

required = [
    "master_physical_15min.csv",
    "load_forecast_derived_from_smard.csv",
    "da_price_calibrated_forecast.csv",
    "oos_calendar.csv",
]

for name in required:
    hits = list(ROOT.rglob(name))
    print(f"{name}: {'FOUND -> ' + str(hits[0]) if hits else 'MISSING'}")

settlement = list(ROOT.rglob("Realized_Settlement_Summary.csv"))
print("Realized_Settlement_Summary.csv:",
      "FOUND -> " + str(settlement[0]) if settlement else "MISSING")

scenario_files = []
for k in (30, 50, 100):
    scenario_files += list(ROOT.rglob(f"*K{k}*.csv"))
print("Scenario-related CSV count:", len(scenario_files))

# RUN_GATE10_REAL_OOS.py
# Gate 10F -> 10J real-data execution runner
# Python 3.10+
#
# Required packages:
# pip install numpy pandas scipy highspy openpyxl matplotlib

from pathlib import Path
import sys, json, time, math, traceback
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SCEN = DATA / "scenarios" / "reduced_scenarios"
OUT = ROOT / "Gate10_REAL_RESULTS"
OUT.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------
# 1. Locate files automatically
# ------------------------------------------------------------

def find_file(name):
    hits = list(ROOT.rglob(name))
    if hits:
        return hits[0]
    return None

def find_any(names):
    for n in names:
        p = find_file(n)
        if p:
            return p
    return None

FILES = {
    "physical": find_any([
        "master_physical_15min.csv",
        "master_physical_15min(1).csv"
    ]),
    "load_forecast": find_any([
        "load_forecast_derived_from_smard.csv",
        "load_forecast_derived_from_smard(1).csv"
    ]),
    "price": find_any([
        "da_price_calibrated_forecast.csv",
        "da_price_calibrated_forecast(1).csv"
    ]),
    "oos": find_any([
        "oos_calendar.csv",
        "oos_calendar(1).csv"
    ]),
    "config": find_any([
        "gate10_config.json",
        "config.json",
        "model_config.json",
        "final_config.json"
    ]),
}

for k, v in FILES.items():
    print(f"{k:15s}: {v}")

# Scenario files
SCENARIO_FILES = {}
for K in [30, 50, 100, 200]:
    p = find_any([
        f"scenario_reduced_{K}.csv",
        f"scenario_reduced_{K}(1).csv"
    ])
    if p:
        SCENARIO_FILES[K] = p

print("\nScenario files:")
for k, p in SCENARIO_FILES.items():
    print(k, p)

# ------------------------------------------------------------
# 2. Hard integrity check
# ------------------------------------------------------------

required = ["physical", "load_forecast", "price"]

missing = [k for k in required if FILES[k] is None]

if missing:
    print("\nBLOCKED: missing required real-data files:")
    for x in missing:
        print("   ", x)
    print("\nThe runner will NOT generate synthetic data.")
    sys.exit(2)

if not SCENARIO_FILES:
    print("\nBLOCKED: no reduced real scenario file found.")
    sys.exit(3)

# ------------------------------------------------------------
# 3. Import repaired Gate-10F engine
# ------------------------------------------------------------

ENGINE = find_any([
    "gate10f1_repaired_final.py",
    "gate10f1_repaired_final(1).py"
])

if ENGINE is None:
    print("BLOCKED: gate10f1_repaired_final.py not found.")
    sys.exit(4)

sys.path.insert(0, str(ENGINE.parent))

import importlib.util

spec = importlib.util.spec_from_file_location(
    "gate10_engine",
    str(ENGINE)
)
engine = importlib.util.module_from_spec(spec)
# IMPORTANT:
# Register the module before executing it.
# Required by Python 3.13 dataclasses.
sys.modules[spec.name] = engine

spec.loader.exec_module(engine)

print("\nLoaded:", ENGINE)

# ------------------------------------------------------------
# 4. Configuration
# ------------------------------------------------------------

if FILES["config"]:
    with open(FILES["config"], "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
else:
    # IMPORTANT:
    # This fallback is ONLY a parameter template.
    # It does NOT create data.
    CONFIG = {
        "horizon_hours": 24,
        "operational_stages": 7,
        "stages": [
            {"stage_id":1,"first_available_hour":0},
            {"stage_id":2,"first_available_hour":1},
            {"stage_id":3,"first_available_hour":2},
            {"stage_id":4,"first_available_hour":3},
            {"stage_id":5,"first_available_hour":4},
            {"stage_id":6,"first_available_hour":5},
            {"stage_id":7,"first_available_hour":6},
        ],
        "dispatch_groups": [
            {
                "name":"DG1",
                "dg_mw":100,
                "dr_mw":50,
                "import_mw":100,
                "export_mw":100,
                "renewable_mw":200
            }
        ],
        "battery":{
            "energy_mwh":20,
            "charge_mw":1,
            "discharge_mw":1,
            "initial_soc_mwh":2,
            "min_soc_fraction":0.1,
            "max_soc_fraction":0.9,
            "eta_charge":0.95,
            "eta_discharge":0.95,
            "degradation_cost_eur_mwh":0
        },
        "market":{
            "reserve_price_eur_per_mw":0,
            "intraday_price_spread_eur_mwh":0,
            "dr_price_eur_per_mwh":0,
            "grid_import_price_eur_mwh":0,
            "grid_export_price_eur_mwh":0,
            "unserved_energy_penalty_eur_mwh":10000
        },
        "renewable_mapping_factor":1.0,
        "risk":{
            "cvar_alpha":0.95,
            "risk_lambda":0.0
        },
        "reliability":{
            "n_minus_1_required":True
        },
        "solver":{
            "time_limit_seconds":300,
            "mip_rel_gap":0.01
        }
    }

# ------------------------------------------------------------
# 5. Load scenario
# ------------------------------------------------------------

def load_scenario(path, K):
    df = pd.read_csv(path)

    needed = [
        "scenario_id",
        "hour",
        "probability",
        "price_error_bc",
        "load_error_bc",
        "wind_on_error_bc",
        "wind_off_error_bc",
        "pv_error_bc"
    ]

    miss = [x for x in needed if x not in df.columns]
    if miss:
        raise ValueError(
            f"{path.name}: missing columns {miss}"
        )

    df = df.sort_values(
        ["scenario_id","hour"]
    ).reset_index(drop=True)

    if df.scenario_id.nunique() != K:
        raise ValueError(
            f"{path.name}: expected K={K}, "
            f"found {df.scenario_id.nunique()}"
        )

    if not np.isclose(
        df[["scenario_id","probability"]]
        .drop_duplicates()["probability"].sum(),
        1.0,
        atol=1e-8
    ):
        raise ValueError(
            f"{path.name}: probabilities do not sum to 1"
        )

    return df

# ------------------------------------------------------------
# 6. Load and standardize forecast base
# ------------------------------------------------------------

def read_table(path):
    df = pd.read_csv(path)

    # detect datetime
    date_col = None
    for c in df.columns:
        if c.lower() in [
            "timestamp","datetime","date_time",
            "time","delivery_time"
        ]:
            date_col = c
            break

    if date_col:
        df[date_col] = pd.to_datetime(
            df[date_col],
            errors="coerce",
            utc=True
        )

    return df

physical = read_table(FILES["physical"])
loadf = read_table(FILES["load_forecast"])
price = read_table(FILES["price"])

print("\nRows:")
print("physical:", len(physical))
print("load:", len(loadf))
print("price:", len(price))

# ------------------------------------------------------------
# 7. Identify required forecast columns
# ------------------------------------------------------------

def first_col(df, candidates):
    low = {c.lower():c for c in df.columns}
    for c in candidates:
        if c.lower() in low:
            return low[c.lower()]
    return None

def merge_source_tables():

    # Prefer calibrated price/forecast file if it already
    # contains all required hourly columns.
    source = price.copy()

    aliases = {
        "load_forecast":[
            "load_forecast",
            "load_forecast_derived",
            "load_fcst"
        ],
        "wind_on_forecast":[
            "wind_on_forecast",
            "wind_onshore_forecast"
        ],
        "wind_off_forecast":[
            "wind_off_forecast",
            "wind_offshore_forecast"
        ],
        "pv_forecast":[
            "pv_forecast",
            "solar_forecast"
        ],
        "forecast_hybrid":[
            "forecast_hybrid",
            "da_price_forecast",
            "price_forecast"
        ]
    }

    result = pd.DataFrame()

    for target, names in aliases.items():
        c = first_col(source, names)

        if c:
            result[target] = source[c].values

    # load forecast from dedicated file if absent
    if "load_forecast" not in result.columns:
        c = first_col(loadf, aliases["load_forecast"])
        if c:
            result["load_forecast"] = loadf[c].values

    # renewable forecasts from physical file if absent
    for target in [
        "wind_on_forecast",
        "wind_off_forecast",
        "pv_forecast"
    ]:
        if target not in result.columns:
            c = first_col(
                physical,
                aliases[target]
            )
            if c:
                result[target] = physical[c].values[:len(result)]

    if "forecast_hybrid" not in result.columns:
        raise ValueError(
            "No pre-decision price forecast column found."
        )

    missing = [
        x for x in [
            "load_forecast",
            "wind_on_forecast",
            "wind_off_forecast",
            "pv_forecast",
            "forecast_hybrid"
        ]
        if x not in result.columns
    ]

    if missing:
        raise ValueError(
            "Required forecast columns unavailable: "
            + str(missing)
        )

    result = result.iloc[:24].copy()
    result.reset_index(drop=True, inplace=True)

    return result

BASE = merge_source_tables()

print("\nBase forecast:")
print(BASE.head())
print("shape:", BASE.shape)

if len(BASE) != 24:
    raise ValueError(
        "Base forecast must contain exactly 24 hourly rows."
    )

# ------------------------------------------------------------
# 8. Run models
# ------------------------------------------------------------

RESULTS = []

def run_one(model, K, scenarios, lam, alpha):

    print(
        f"\nRunning {model} | K={K} | "
        f"lambda={lam} | alpha={alpha}"
    )

    cfg = json.loads(json.dumps(CONFIG))
    cfg.setdefault("risk", {})
    cfg["risk"]["risk_lambda"] = lam
    cfg["risk"]["cvar_alpha"] = alpha

    start = time.perf_counter()

    try:
        res = engine.solve(
            cfg,
            BASE,
            scenarios,
            risk_lambda=lam
        )

        elapsed = time.perf_counter() - start

        row = {
            "model":model,
            "K":K,
            "lambda":lam,
            "alpha":alpha,
            "status":res.get("status"),
            "objective":res.get("objective"),
            "runtime_seconds":elapsed,
            "variables":res.get("variables"),
            "run_status":res.get("run_status"),
        }

        print(row)

        RESULTS.append(row)

        return row

    except Exception as e:

        row = {
            "model":model,
            "K":K,
            "lambda":lam,
            "alpha":alpha,
            "status":"FAILED",
            "objective":np.nan,
            "runtime_seconds":time.perf_counter()-start,
            "variables":np.nan,
            "run_status":repr(e)
        }

        print(row)

        RESULTS.append(row)

        return row

# ------------------------------------------------------------
# B0 deterministic
# ------------------------------------------------------------

# Deterministic B0 is represented by zero-error scenario.
zero = pd.DataFrame({
    "scenario_id":[0]*24,
    "hour":range(24),
    "probability":[1/1]*24,
    "price_error_bc":[0]*24,
    "load_error_bc":[0]*24,
    "wind_on_error_bc":[0]*24,
    "wind_off_error_bc":[0]*24,
    "pv_error_bc":[0]*24
})

run_one(
    "B0",
    1,
    zero,
    0.0,
    0.95
)

# ------------------------------------------------------------
# B2 / P1
# ------------------------------------------------------------

for K, path in sorted(SCENARIO_FILES.items()):

    scenarios = load_scenario(path, K)

    run_one(
        "B2",
        K,
        scenarios,
        0.0,
        0.95
    )

    run_one(
        "P1",
        K,
        scenarios,
        1.0,
        0.95
    )

# ------------------------------------------------------------
# Save optimization results
# ------------------------------------------------------------

RESULT_DF = pd.DataFrame(RESULTS)

RESULT_DF.to_csv(
    OUT/"Gate10_Optimization_Results.csv",
    index=False
)

# ------------------------------------------------------------
# 9. Scenario diagnostics
# ------------------------------------------------------------

scenario_rows=[]

for K,path in sorted(SCENARIO_FILES.items()):

    df=load_scenario(path,K)

    scenario_rows.append({
        "K":K,
        "unique_scenarios":df.scenario_id.nunique(),
        "rows":len(df),
        "probability_sum":
            df[["scenario_id","probability"]]
            .drop_duplicates()
            .probability.sum(),
        "hours_per_scenario":
            df.groupby("scenario_id").size().mean(),
        "mean_abs_price_error":
            df.price_error_bc.abs().mean(),
        "mean_abs_load_error":
            df.load_error_bc.abs().mean(),
        "mean_abs_pv_error":
            df.pv_error_bc.abs().mean()
    })

SCEN_DF=pd.DataFrame(scenario_rows)

SCEN_DF.to_csv(
    OUT/"Scenario_Diagnostics.csv",
    index=False
)

# ------------------------------------------------------------
# 10. Figures
# ------------------------------------------------------------

if not RESULT_DF.empty:

    # Runtime
    plt.figure(figsize=(8,5))

    for model in RESULT_DF.model.unique():

        x=RESULT_DF[
            RESULT_DF.model==model
        ]

        plt.plot(
            x["K"],
            x["runtime_seconds"],
            marker="o",
            label=model
        )

    plt.xlabel("Scenario count K")
    plt.ylabel("Runtime (s)")
    plt.title("Gate 10 — MILP Runtime")
    plt.legend()
    plt.grid(alpha=.25)
    plt.tight_layout()
    plt.savefig(
        OUT/"Fig_Runtime_vs_K.png",
        dpi=300
    )
    plt.close()

    # Objective
    plt.figure(figsize=(8,5))

    for model in RESULT_DF.model.unique():

        x=RESULT_DF[
            RESULT_DF.model==model
        ]

        plt.plot(
            x["K"],
            x["objective"],
            marker="o",
            label=model
        )

    plt.xlabel("Scenario count K")
    plt.ylabel("Optimization objective")
    plt.title("Gate 10 — Optimization Objective")
    plt.legend()
    plt.grid(alpha=.25)
    plt.tight_layout()
    plt.savefig(
        OUT/"Fig_Objective_vs_K.png",
        dpi=300
    )
    plt.close()

# Scenario quality
if not SCEN_DF.empty:

    plt.figure(figsize=(8,5))

    plt.plot(
        SCEN_DF["K"],
        SCEN_DF["mean_abs_price_error"],
        marker="o",
        label="Price error"
    )

    plt.plot(
        SCEN_DF["K"],
        SCEN_DF["mean_abs_load_error"],
        marker="o",
        label="Load error"
    )

    plt.plot(
        SCEN_DF["K"],
        SCEN_DF["mean_abs_pv_error"],
        marker="o",
        label="PV error"
    )

    plt.xlabel("Scenario count K")
    plt.ylabel("Mean absolute calibrated error")
    plt.title("Scenario-set diagnostics")
    plt.legend()
    plt.grid(alpha=.25)
    plt.tight_layout()
    plt.savefig(
        OUT/"Fig_Scenario_Diagnostics.png",
        dpi=300
    )
    plt.close()

# ------------------------------------------------------------
# 11. Excel package
# ------------------------------------------------------------

xlsx=OUT/"Gate10_REAL_RESULTS.xlsx"

with pd.ExcelWriter(
    xlsx,
    engine="openpyxl"
) as writer:

    RESULT_DF.to_excel(
        writer,
        sheet_name="Optimization",
        index=False
    )

    SCEN_DF.to_excel(
        writer,
        sheet_name="Scenario_Diagnostics",
        index=False
    )

# ------------------------------------------------------------
# 12. Final report
# ------------------------------------------------------------

report = {
    "gate":"10F-10J",
    "timestamp":pd.Timestamp.utcnow().isoformat(),
    "root":str(ROOT),
    "optimization_results":
        RESULT_DF.to_dict("records"),
    "scenario_diagnostics":
        SCEN_DF.to_dict("records")
}

with open(
    OUT/"Gate10_RUN_REPORT.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        report,
        f,
        indent=2,
        ensure_ascii=False,
        default=str
    )

print("\n" + "="*70)
print("GATE 10 EXECUTION FINISHED")
print("="*70)

print("\nRESULTS:")
print(RESULT_DF.to_string(index=False))

print("\nOUTPUT DIRECTORY:")
print(OUT)

print("\nFiles:")
for p in sorted(OUT.iterdir()):
    print(" ", p.name)

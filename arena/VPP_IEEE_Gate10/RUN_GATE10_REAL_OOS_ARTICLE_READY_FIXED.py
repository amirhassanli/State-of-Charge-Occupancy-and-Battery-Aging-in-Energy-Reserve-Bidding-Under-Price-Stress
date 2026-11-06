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
from scipy.stats import gaussian_kde

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
            "reserve_price_eur_per_mw":5,
            "intraday_price_spread_eur_mwh":2,
            "dr_price_eur_per_mwh":3,
            "grid_import_price_eur_mwh":80,
            "grid_export_price_eur_mwh":40,
            "unserved_energy_penalty_eur_mwh":500,
            "dg_cost_eur_mwh":30
        },
        "renewable_mapping_factor":0.01,
        "load_mapping_factor":0.005,
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
# 4B. Economic scaling / risk configuration repair
# ------------------------------------------------------------
# System-level SMARD forecasts must be mapped explicitly to the VPP scale.
# The load and renewable mapping factors are independent parameters.
# If an existing config has no load factor, use the renewable factor as a
# backward-compatible starting point and print it explicitly for audit.
if "load_mapping_factor" not in CONFIG:
    CONFIG["load_mapping_factor"] = float(CONFIG.get("renewable_mapping_factor", 0.01))

CONFIG.setdefault("risk", {})
CONFIG["risk"]["cvar_alpha"] = float(CONFIG["risk"].get("cvar_alpha", 0.95))

print("\nECONOMIC SCALING:")
print("  renewable_mapping_factor =", CONFIG.get("renewable_mapping_factor"))
print("  load_mapping_factor      =", CONFIG.get("load_mapping_factor"))
print("  CVaR alpha               =", CONFIG["risk"]["cvar_alpha"])

if FILES["config"] is None:
    print("  WARNING: no external config found; article-run fallback market parameters are provisional.")

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
    """Create the 24-hour hourly base by timestamp alignment.
    15-min physical/load data are aggregated to hourly means; DA price is
    already hourly. No positional assignment is allowed.
    """
    aliases = {
        "load_forecast": ["load_forecast", "load_forecast_derived", "load_fcst"],
        "wind_on_forecast": ["wind_on_forecast", "wind_onshore_forecast"],
        "wind_off_forecast": ["wind_off_forecast", "wind_offshore_forecast"],
        "pv_forecast": ["pv_forecast", "solar_forecast"],
        "forecast_hybrid": ["forecast_hybrid", "da_price_forecast", "price_forecast"],
    }

    def datetime_col(df):
        for c in df.columns:
            if c.lower() in ["timestamp", "datetime", "date_time", "time", "delivery_time"]:
                return c
        return None

    def hourly(df, value_col):
        dc = datetime_col(df)
        if dc is None:
            raise ValueError(f"No timestamp column found for {value_col}.")
        x = df[[dc, value_col]].copy()
        x[dc] = pd.to_datetime(x[dc], errors="coerce", utc=True)
        x[value_col] = pd.to_numeric(x[value_col], errors="coerce")
        x = x.dropna(subset=[dc]).sort_values(dc)
        x["hour"] = x[dc].dt.floor("h")
        return x.groupby("hour", as_index=False)[value_col].mean()

    pdc = datetime_col(price)
    if pdc is None:
        raise ValueError("DA price table has no timestamp column.")
    p = price.copy()
    p[pdc] = pd.to_datetime(p[pdc], errors="coerce", utc=True)
    p = p.dropna(subset=[pdc]).copy()
    p["hour"] = p[pdc].dt.floor("h")
    p = p.sort_values("hour").drop_duplicates("hour", keep="first")
    result = p[["hour"]].copy()

    for target, names in aliases.items():
        c = first_col(p, names)
        if c:
            result[target] = pd.to_numeric(p[c], errors="coerce").to_numpy()

    if "load_forecast" not in result:
        c = first_col(loadf, aliases["load_forecast"])
        if not c: raise ValueError("No load forecast column found.")
        h = hourly(loadf, c).rename(columns={c:"load_forecast"})
        result = result.merge(h, on="hour", how="left")

    for target in ["wind_on_forecast", "wind_off_forecast", "pv_forecast"]:
        if target not in result:
            c = first_col(physical, aliases[target])
            if not c: raise ValueError(f"No required forecast column: {target}")
            h = hourly(physical, c).rename(columns={c:target})
            result = result.merge(h, on="hour", how="left")

    if "forecast_hybrid" not in result:
        raise ValueError("No pre-decision price forecast column found.")

    required_fc = ["load_forecast","wind_on_forecast","wind_off_forecast","pv_forecast","forecast_hybrid"]
    missing = [c for c in required_fc if c not in result]
    if missing: raise ValueError(f"Required forecast columns unavailable: {missing}")
    # IMPORTANT: do not fill/interpolate missing price forecasts and do not
    # substitute realized DA prices.  The calibrated price forecast is a
    # decision-eligible forecast only where it is actually available.
    # The current calibration file contains an initial block of 24 rows for
    # which forecast_hybrid is NaN.  Those rows are excluded, and the first
    # 24 COMPLETE hourly forecast records are used.  This preserves the
    # information firewall and avoids artificial data.
    result = result.sort_values("hour").reset_index(drop=True)

    missing_mask = result[required_fc].isna().any(axis=1)
    n_incomplete = int(missing_mask.sum())
    if n_incomplete:
        bad_hours = result.loc[missing_mask, "hour"].astype(str).tolist()[:10]
        print(f"\nForecast alignment: excluding {n_incomplete} incomplete hourly rows.")
        print("First excluded hours:", bad_hours)
        print("Reason counts:")
        print(result.loc[missing_mask, required_fc].isna().sum())

    complete = result.loc[~missing_mask, ["hour"] + required_fc].copy()

    if len(complete) < 24:
        raise ValueError(
            f"Only {len(complete)} complete hourly forecast rows are available; "
            "24 are required. No NaN filling or realized-price substitution is allowed."
        )

    result = complete.iloc[:24].copy().reset_index(drop=True)

    if result[required_fc].isna().any().any():
        raise RuntimeError("Internal error: incomplete rows survived complete-case filtering.")

    print("\nForecast alignment: PASS")
    print("Selected window:", result.loc[0, "hour"], "to", result.loc[len(result)-1, "hour"])
    print("Complete hourly rows selected:", len(result))

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
SOLUTIONS = {}

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
            "expected_profit":res.get("expected_profit"),
            "cvar95":res.get("cvar95"),
            "risk_adjusted_objective":res.get("risk_adjusted_objective"),
            "worst_case_profit":res.get("worst_case_profit"),
            "best_case_profit":res.get("best_case_profit"),
            "runtime_seconds":elapsed,
            "variables":res.get("variables"),
            "run_status":res.get("run_status"),
        }

        print(row)

        RESULTS.append(row)
        SOLUTIONS[(model, K)] = res

        return row

    except Exception as e:

        row = {
            "model":model,
            "K":K,
            "lambda":lam,
            "alpha":alpha,
            "status":"FAILED",
            "objective":np.nan,
            "expected_profit":np.nan,
            "cvar95":np.nan,
            "risk_adjusted_objective":np.nan,
            "worst_case_profit":np.nan,
            "best_case_profit":np.nan,
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
        0.02,
        0.95
    )

# ------------------------------------------------------------
# Save optimization results
# ------------------------------------------------------------

RESULT_DF = pd.DataFrame(RESULTS)

# ------------------------------------------------------------
# 8B. Realized one-day settlement diagnostic
# ------------------------------------------------------------
# This is a true realization-based settlement for the 24-hour base day using
# SMARD actual physical values and realized DA price. It is deliberately
# reported separately from the stochastic objective/CVaR and is NOT used to
# claim the final rolling OOS result until the full OOS calendar is available.
def hourly_actuals_for_base():
    def dtcol(df):
        for c in df.columns:
            if c.lower() in ["timestamp","datetime","date_time","time","delivery_time"]:
                return c
        raise ValueError("No timestamp column found for realized settlement.")
    d=physical.copy()
    dc=dtcol(d)
    d[dc]=pd.to_datetime(d[dc],errors="coerce",utc=True)
    d["hour"]=d[dc].dt.floor("h")
    cols=["load_actual","wind_on_actual","wind_off_actual","pv_actual"]
    miss=[c for c in cols if c not in d.columns]
    if miss: raise ValueError(f"Missing actual columns for settlement: {miss}")
    a=d.groupby("hour",as_index=False)[cols].mean()
    p=price.copy(); pdc=dtcol(p); p[pdc]=pd.to_datetime(p[pdc],errors="coerce",utc=True); p["hour"]=p[pdc].dt.floor("h")
    pc=first_col(p,["da_price_eur_mwh","DA_price","price","da_price"])
    if pc is None: raise ValueError("No realized DA price column found for settlement.")
    pp=p[["hour",pc]].drop_duplicates("hour").rename(columns={pc:"realized_da_price"})
    out=BASE[["hour"]].merge(a,on="hour",how="left").merge(pp,on="hour",how="left")
    if out[["load_actual","wind_on_actual","wind_off_actual","pv_actual","realized_da_price"]].isna().any().any():
        raise ValueError("Realized settlement day is not fully covered by actual SMARD data.")
    return out

def realized_settlement(model,K,lam):
    res=SOLUTIONS.get((model,K))
    if not res or "decisions" not in res: return None
    a=hourly_actuals_for_base()
    cfg=json.loads(json.dumps(CONFIG)); mkt=cfg["market"]; rf=float(cfg["renewable_mapping_factor"]); lf=float(cfg["load_mapping_factor"])
    G=cfg["dispatch_groups"]; renewable_cap=sum(float(g["renewable_mw"]) for g in G)
    rows=[]
    total=0.0; imbalance=0.0; unserved=0.0
    for t in range(24):
        q=a.iloc[t]; ren=min(max(0,float(q.wind_on_actual))+max(0,float(q.wind_off_actual))+max(0,float(q.pv_actual)), renewable_cap/rf if rf>0 else 0)*rf
        load=float(q.load_actual)*lf
        da=res["decisions"]["DA"][t]; ids=res["decisions"]["IDSELL"][t]; idb=res["decisions"]["IDBUY"][t]; dru=res["decisions"]["DRU"][t]; drd=res["decisions"]["DRD"][t]; dg=res["decisions"]["DG"][t]; ch=res["decisions"]["CH"][t]; dch=res["decisions"]["DCH"][t]; reserve=res["decisions"]["RES"][t]
        price_real=float(q.realized_da_price); spread=float(mkt["intraday_price_spread_eur_mwh"]);
        surplus=ren+dg+dch+dru+idb-load-ch-da-ids
        if surplus>=0: imb_sell=surplus; imb_buy=0.0
        else: imb_sell=0.0; imb_buy=-surplus
        imb_revenue=(price_real-spread)*imb_sell-(price_real+spread)*imb_buy
        prof=(price_real*da +(price_real-spread)*ids -(price_real+spread)*idb +float(mkt["reserve_price_eur_per_mw"])*reserve +float(mkt["dr_price_eur_per_mwh"])*(dru-drd)-float(mkt.get("dg_cost_eur_mwh",0))*dg-float(cfg["battery"]["degradation_cost_eur_mwh"])*(ch+dch)+imb_revenue)
        total+=prof; imbalance+=abs(surplus); unserved+=max(0.0, -surplus)
        rows.append({"hour":q.hour,"realized_da_price":price_real,"realized_load_mw":load,"realized_renewable_mw":ren,"imbalance_mw":surplus,"hourly_profit_eur":prof})
    return {"model":model,"K":K,"lambda":lam,"realized_settlement_profit_eur":total,"mean_abs_imbalance_mw":imbalance/24.0,"total_unserved_mwh":unserved,"detail":pd.DataFrame(rows)}

SETTLEMENTS=[]
for model,K,lam in [("B0",1,0.0)]+[("B2",K,0.0) for K in sorted(SCENARIO_FILES)]+[("P1",K,0.02) for K in sorted(SCENARIO_FILES)]:
    z=realized_settlement(model,K,lam)
    if z:
        SETTLEMENTS.append({k:v for k,v in z.items() if k!="detail"})
        z["detail"].to_csv(OUT/f"Settlement_{model}_K{K}.csv",index=False)
SETTLEMENT_DF=pd.DataFrame(SETTLEMENTS)
SETTLEMENT_DF.to_csv(OUT/"Realized_Settlement_Summary.csv",index=False)

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
# 10. Article-grade tables and figures
# ------------------------------------------------------------

def savefig(path):
    plt.tight_layout()
    plt.savefig(path, dpi=400, bbox_inches="tight")
    plt.close()

# ---- Table-ready diagnostics from real scenario files ----
scenario_long = []
for K, path in sorted(SCENARIO_FILES.items()):
    df = load_scenario(path, K)
    for col in ["price_error_bc","load_error_bc","wind_on_error_bc","wind_off_error_bc","pv_error_bc"]:
        x = pd.to_numeric(df[col], errors="coerce")
        scenario_long.append({
            "K":K, "variable":col.replace("_error_bc", ""),
            "mean":x.mean(), "std":x.std(ddof=1),
            "p01":x.quantile(.01), "p05":x.quantile(.05),
            "median":x.quantile(.50), "p95":x.quantile(.95), "p99":x.quantile(.99),
            "mae":x.abs().mean(), "min":x.min(), "max":x.max()
        })
SCEN_STAT_DF = pd.DataFrame(scenario_long)
SCEN_STAT_DF.to_csv(OUT/"Scenario_Error_Statistics.csv", index=False)

# Forecast-base table
BASE_TABLE = BASE.copy()
BASE_TABLE.insert(0, "hour_index", np.arange(1, len(BASE_TABLE)+1))
BASE_TABLE.to_csv(OUT/"Base_24h_Forecast.csv", index=False)

# Excel-safe copy: remove timezone information without changing the UTC clock values.
BASE_TABLE_EXCEL = BASE_TABLE.copy()
for _c in BASE_TABLE_EXCEL.columns:
    if pd.api.types.is_datetime64tz_dtype(BASE_TABLE_EXCEL[_c]):
        BASE_TABLE_EXCEL[_c] = BASE_TABLE_EXCEL[_c].dt.tz_localize(None)

# Article-ready economic summary.
if not RESULT_DF.empty:
    OPT_SUMMARY = (RESULT_DF.groupby(["model","K"], as_index=False)
                   .agg(expected_profit=("expected_profit","first"),
                        cvar95=("cvar95","first"),
                        risk_adjusted_objective=("risk_adjusted_objective","first"),
                        worst_case_profit=("worst_case_profit","first"),
                        best_case_profit=("best_case_profit","first"),
                        runtime_seconds=("runtime_seconds","first"),
                        status=("status","first"),
                        variables=("variables","first")))
else:
    OPT_SUMMARY = pd.DataFrame()

OPT_SUMMARY.to_csv(OUT/"Optimization_Summary.csv", index=False)

# ---- Figure 1: calibrated error distributions ----
if not SCEN_STAT_DF.empty:
    vars_ = ["price","load","wind_on","wind_off","pv"]
    for var in vars_:
        plt.figure(figsize=(7.2,4.5))
        for K in sorted(SCENARIO_FILES):
            d = load_scenario(SCENARIO_FILES[K], K)
            x = pd.to_numeric(d[f"{var}_error_bc"], errors="coerce").dropna().to_numpy()
            if len(x) > 2:
                grid=np.linspace(np.quantile(x,.005), np.quantile(x,.995), 250)
                kde=gaussian_kde(x)
                plt.plot(grid,kde(grid),label=f"K={K}")
        plt.xlabel(f"{var.replace('_',' ').title()} calibrated error")
        plt.ylabel("Density")
        plt.title(f"Calibrated {var.replace('_',' ').title()} Error Distribution")
        plt.legend(frameon=False)
        plt.grid(alpha=.2)
        savefig(OUT/f"Fig_{var}_error_distribution.png")

# ---- Figure 2: scenario trajectories and probability-weighted mean ----
Kplot=max(SCENARIO_FILES) if SCENARIO_FILES else None
if Kplot:
    d=load_scenario(SCENARIO_FILES[Kplot],Kplot)
    plt.figure(figsize=(8,4.8))
    for sid, g in d.groupby("scenario_id"):
        plt.plot(g["hour"], g["load_error_bc"], alpha=.08, linewidth=.7)
    mean=d.groupby("hour")["load_error_bc"].mean()
    plt.plot(mean.index,mean.values,linewidth=2.2,label="Scenario mean")
    plt.xlabel("Hour")
    plt.ylabel("Load error (MW)")
    plt.title(f"Reduced Scenario Fan — Load Error (K={Kplot})")
    plt.legend(frameon=False)
    plt.grid(alpha=.2)
    savefig(OUT/"Fig_Scenario_Fan_Load_Error.png")

# ---- Figure 3: correlation matrix of scenario errors ----
if Kplot:
    d=load_scenario(SCENARIO_FILES[Kplot],Kplot)
    cols=["price_error_bc","load_error_bc","wind_on_error_bc","wind_off_error_bc","pv_error_bc"]
    C=d[cols].corr()
    plt.figure(figsize=(6.4,5.2))
    im=plt.imshow(C.to_numpy(), aspect="auto", interpolation="nearest")
    plt.colorbar(im, fraction=.046, pad=.04, label="Correlation")
    labels=[c.replace("_error_bc","").replace("_"," ").title() for c in cols]
    plt.xticks(range(len(cols)),labels,rotation=35,ha="right")
    plt.yticks(range(len(cols)),labels)
    for i in range(len(cols)):
        for j in range(len(cols)):
            plt.text(j,i,f"{C.iloc[i,j]:.2f}",ha="center",va="center",fontsize=8)
    plt.title(f"Dependence Structure of Reduced Scenarios (K={Kplot})")
    savefig(OUT/"Fig_Scenario_Correlation_Matrix.png")

# ---- Figure 4: optimization runtime ----
if not RESULT_DF.empty:
    plt.figure(figsize=(7.2,4.5))
    for model in RESULT_DF.model.dropna().unique():
        x=RESULT_DF[RESULT_DF.model==model].sort_values("K")
        plt.plot(x.K,x.runtime_seconds,marker="o",linewidth=1.8,label=model)
    plt.xlabel("Number of reduced scenarios, K")
    plt.ylabel("MILP runtime (s)")
    plt.title("Computational Performance")
    plt.legend(frameon=False)
    plt.grid(alpha=.2)
    savefig(OUT/"Fig_Runtime_vs_K.png")

# ---- Figure 5: objective vs scenario count ----
if not RESULT_DF.empty:
    plt.figure(figsize=(7.2,4.5))
    for model in RESULT_DF.model.dropna().unique():
        x=RESULT_DF[RESULT_DF.model==model].sort_values("K")
        plt.plot(x.K,x.objective,marker="o",linewidth=1.8,label=model)
    plt.xlabel("Number of reduced scenarios, K")
    plt.ylabel("Risk-adjusted objective")
    plt.title("Risk-adjusted Objective Stability Under Scenario Reduction")
    plt.legend(frameon=False)
    plt.grid(alpha=.2)
    savefig(OUT/"Fig_Objective_vs_K.png")

# ---- Figure 6: scenario-set quality ----
if not SCEN_DF.empty:
    plt.figure(figsize=(7.2,4.5))
    for col,label in [("mean_abs_price_error","Price"),("mean_abs_load_error","Load"),("mean_abs_pv_error","PV")]:
        plt.plot(SCEN_DF.K,SCEN_DF[col],marker="o",linewidth=1.7,label=label)
    plt.xlabel("Number of reduced scenarios, K")
    plt.ylabel("Mean absolute calibrated error")
    plt.title("Scenario-Set Quality")
    plt.legend(frameon=False)
    plt.grid(alpha=.2)
    savefig(OUT/"Fig_Scenario_Diagnostics.png")

# ---- Figure 7: expected profit and CVaR by model/scenario count ----
if not RESULT_DF.empty and "expected_profit" in RESULT_DF.columns:
    plt.figure(figsize=(7.2,4.5))
    for model in RESULT_DF.model.dropna().unique():
        x=RESULT_DF[RESULT_DF.model==model].sort_values("K")
        plt.plot(x.K,x.expected_profit,marker="o",linewidth=1.8,label=model)
    plt.xlabel("Number of reduced scenarios, K")
    plt.ylabel("Expected profit (EUR)")
    plt.title("Expected Profit Under Scenario Reduction")
    plt.legend(frameon=False); plt.grid(alpha=.2); savefig(OUT/"Fig_Expected_Profit_vs_K.png")

if not RESULT_DF.empty and "cvar95" in RESULT_DF.columns:
    plt.figure(figsize=(7.2,4.5))
    for model in RESULT_DF.model.dropna().unique():
        x=RESULT_DF[RESULT_DF.model==model].sort_values("K")
        plt.plot(x.K,x.cvar95,marker="o",linewidth=1.8,label=model)
    plt.xlabel("Number of reduced scenarios, K")
    plt.ylabel("CVaR95 loss (EUR)")
    plt.title("Tail Risk Under Scenario Reduction")
    plt.legend(frameon=False); plt.grid(alpha=.2); savefig(OUT/"Fig_CVaR95_vs_K.png")

# 11. Excel package
# ------------------------------------------------------------

xlsx=OUT/"Gate10_REAL_RESULTS.xlsx"

def excel_safe_dataframe(df):
    x = df.copy()
    for c in x.columns:
        if isinstance(x[c].dtype, pd.DatetimeTZDtype):
            x[c] = x[c].dt.tz_localize(None)
    return x

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

    BASE_TABLE_EXCEL.to_excel(writer, sheet_name="Base_24h", index=False)
    SCEN_STAT_DF.to_excel(writer, sheet_name="Scenario_Statistics", index=False)
    OPT_SUMMARY.to_excel(writer, sheet_name="Optimization_Summary", index=False)
    SETTLEMENT_DF.to_excel(writer, sheet_name="Realized_Settlement", index=False)

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
        SCEN_DF.to_dict("records"),
    "realized_settlement":
        SETTLEMENT_DF.to_dict("records")
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

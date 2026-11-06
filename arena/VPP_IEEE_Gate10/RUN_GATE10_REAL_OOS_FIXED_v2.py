# RUN_GATE10_REAL_OOS_FIXED.py
# Gate 10F -> 10J real-data execution runner
# Python 3.10+
#
# Required:
# pip install numpy pandas scipy highspy openpyxl matplotlib

from pathlib import Path
import sys, json, time, traceback
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "Gate10_REAL_RESULTS"
OUT.mkdir(parents=True, exist_ok=True)

def find_file(name):
    hits = list(ROOT.rglob(name))
    return hits[0] if hits else None

def find_any(names):
    for n in names:
        p = find_file(n)
        if p:
            return p
    return None

FILES = {
    "physical": find_any(["master_physical_15min.csv","master_physical_15min(1).csv"]),
    "load_forecast": find_any(["load_forecast_derived_from_smard.csv","load_forecast_derived_from_smard(1).csv"]),
    "price": find_any(["da_price_calibrated_forecast.csv","da_price_calibrated_forecast(1).csv"]),
    "config": find_any(["gate10_config.json","config.json","model_config.json","final_config.json"]),
}
SCENARIO_FILES = {}
for K in (30,50,100):
    p = find_any([f"scenario_reduced_{K}.csv",f"scenario_reduced_{K}(1).csv"])
    if p:
        SCENARIO_FILES[K] = p

print("INPUT FILES")
for k,v in FILES.items(): print(f"{k:15s}: {v}")
print("\nSCENARIOS")
for k,v in SCENARIO_FILES.items(): print(k, v)

missing = [k for k in ("physical","load_forecast","price") if FILES[k] is None]
if missing:
    print("BLOCKED: missing:", missing); sys.exit(2)
if not SCENARIO_FILES:
    print("BLOCKED: no reduced real scenario file found."); sys.exit(3)

ENGINE = find_any([
    "gate10f1_repaired_final_CVaRfixed_FIXED.py",
    "gate10f1_repaired_final_CVaRfixed.py",
    "gate10f1_repaired_final_CVaRfixed(1).py",
])
# Last-resort discovery: accept a repaired Gate-10F engine with a matching
# CVaR name anywhere below the project root.
if ENGINE is None:
    candidates = sorted(ROOT.rglob("*gate10f1*CVaR*.py"))
    if candidates:
        ENGINE = candidates[0]

if ENGINE is None:
    print("BLOCKED: repaired Gate-10F CVaR engine not found.")
    print("Expected one of:")
    print("  gate10f1_repaired_final_CVaRfixed_FIXED.py")
    print("  gate10f1_repaired_final_CVaRfixed.py")
    print("  gate10f1_repaired_final_CVaRfixed(1).py")
    print("Copy the supplied engine file into the project root and rerun.")
    sys.exit(4)

import importlib.util
sys.path.insert(0, str(ENGINE.parent))
spec = importlib.util.spec_from_file_location("gate10_engine", str(ENGINE))
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)
print("\nLoaded engine:", ENGINE)

if FILES["config"]:
    with open(FILES["config"],"r",encoding="utf-8") as f:
        CONFIG = json.load(f)
else:
    # Provisional fallback only. This does not create data; it supplies
    # model parameters so the repaired engine can execute. Replace with the
    # locked external config before the final article/OOS run.
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
        "dispatch_groups": [{
            "name":"DG1","dg_mw":100,"dr_mw":50,
            "import_mw":100,"export_mw":100,"renewable_mw":200
        }],
        "battery": {
            "energy_mwh":20,"charge_mw":1,"discharge_mw":1,
            "initial_soc_mwh":2,"min_soc_fraction":0.1,
            "max_soc_fraction":0.9,"eta_charge":0.95,
            "eta_discharge":0.95,"degradation_cost_eur_mwh":0
        },
        "market": {
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
        "risk":{"cvar_alpha":0.95,"risk_lambda":0.0},
        "reliability":{"n_minus_1_required":True},
        "solver":{"time_limit_seconds":300,"mip_rel_gap":0.01}
    }
    print("\nWARNING: no external config found.")
    print("Using provisional fallback parameters for execution/debugging only.")

CONFIG.setdefault("risk", {})
CONFIG["risk"]["cvar_alpha"] = float(CONFIG["risk"].get("cvar_alpha",0.95))
CONFIG["risk"]["risk_lambda"] = float(CONFIG["risk"].get("risk_lambda",0.0))
if "load_mapping_factor" not in CONFIG:
    CONFIG["load_mapping_factor"] = float(CONFIG.get("renewable_mapping_factor",0.01))

print("\nSCALING / RISK")
print("renewable_mapping_factor =", CONFIG.get("renewable_mapping_factor"))
print("load_mapping_factor      =", CONFIG.get("load_mapping_factor"))
print("CVaR alpha               =", CONFIG["risk"]["cvar_alpha"])

def read_table(path):
    df = pd.read_csv(path)
    dc = next((c for c in df.columns if c.lower() in
               ["timestamp","datetime","date_time","time","delivery_time"]), None)
    if dc:
        df[dc] = pd.to_datetime(df[dc], errors="coerce", utc=True)
    return df

physical = read_table(FILES["physical"])
loadf = read_table(FILES["load_forecast"])
price = read_table(FILES["price"])

def first_col(df,candidates):
    low={c.lower():c for c in df.columns}
    for c in candidates:
        if c.lower() in low: return low[c.lower()]
    return None

def dtcol(df):
    return next((c for c in df.columns if c.lower() in
                 ["timestamp","datetime","date_time","time","delivery_time"]), None)

def hourly(df,value_col):
    dc=dtcol(df)
    if dc is None: raise ValueError(f"No timestamp for {value_col}")
    x=df[[dc,value_col]].copy()
    x[dc]=pd.to_datetime(x[dc],errors="coerce",utc=True)
    x[value_col]=pd.to_numeric(x[value_col],errors="coerce")
    x=x.dropna(subset=[dc]).sort_values(dc)
    x["hour"]=x[dc].dt.floor("h")
    return x.groupby("hour",as_index=False)[value_col].mean()

def merge_source_tables():
    aliases={
        "load_forecast":["load_forecast","load_forecast_derived","load_fcst"],
        "wind_on_forecast":["wind_on_forecast","wind_onshore_forecast"],
        "wind_off_forecast":["wind_off_forecast","wind_offshore_forecast"],
        "pv_forecast":["pv_forecast","solar_forecast"],
        "forecast_hybrid":["forecast_hybrid","da_price_forecast","price_forecast"],
    }
    pdc=dtcol(price)
    if pdc is None: raise ValueError("DA price table has no timestamp.")
    p=price.copy()
    p[pdc]=pd.to_datetime(p[pdc],errors="coerce",utc=True)
    p=p.dropna(subset=[pdc]).copy()
    p["hour"]=p[pdc].dt.floor("h")
    p=p.sort_values("hour").drop_duplicates("hour",keep="first")
    result=p[["hour"]].copy()

    for target,names in aliases.items():
        c=first_col(p,names)
        if c:
            result[target]=pd.to_numeric(p[c],errors="coerce").to_numpy()

    if "load_forecast" not in result:
        c=first_col(loadf,aliases["load_forecast"])
        if not c: raise ValueError("No load forecast column.")
        result=result.merge(hourly(loadf,c).rename(columns={c:"load_forecast"}),on="hour",how="left")

    for target in ("wind_on_forecast","wind_off_forecast","pv_forecast"):
        if target not in result:
            c=first_col(physical,aliases[target])
            if not c: raise ValueError(f"No forecast column: {target}")
            result=result.merge(hourly(physical,c).rename(columns={c:target}),on="hour",how="left")

    req=["load_forecast","wind_on_forecast","wind_off_forecast","pv_forecast","forecast_hybrid"]
    miss=[c for c in req if c not in result]
    if miss: raise ValueError(f"Forecast columns unavailable: {miss}")

    result=result.sort_values("hour").reset_index(drop=True)
    incomplete=result[req].isna().any(axis=1)
    if incomplete.any():
        print("Excluding incomplete rows:", int(incomplete.sum()))
    complete=result.loc[~incomplete,["hour"]+req].copy()
    if len(complete)<24:
        raise ValueError("Fewer than 24 complete decision-eligible forecast hours.")
    return complete.iloc[:24].reset_index(drop=True)

BASE=merge_source_tables()
print("\nBASE")
print(BASE)
if len(BASE)!=24: raise ValueError("Base must contain exactly 24 hours.")

def load_scenario(path,K):
    df=pd.read_csv(path)
    needed=["scenario_id","hour","probability","price_error_bc","load_error_bc",
            "wind_on_error_bc","wind_off_error_bc","pv_error_bc"]
    miss=[x for x in needed if x not in df.columns]
    if miss: raise ValueError(f"{path.name}: missing {miss}")
    df=df.sort_values(["scenario_id","hour"]).reset_index(drop=True)
    if df.scenario_id.nunique()!=K: raise ValueError(f"{path.name}: expected K={K}")
    lens=df.groupby("scenario_id").size()
    if not (lens==24).all(): raise ValueError(f"{path.name}: not all scenarios have 24 hours")
    p=df[["scenario_id","probability"]].drop_duplicates()
    if not np.isclose(p.probability.sum(),1.0,atol=1e-8):
        raise ValueError(f"{path.name}: probability sum != 1")
    return df

RESULTS=[]
SOLUTIONS={}

# IMPORTANT: B0 must be solved first, then its realized model-derived
# reference profit is passed exogenously to B2/P1 CVaR.
zero=pd.DataFrame({
    "scenario_id":[0]*24,"hour":range(24),"probability":[1.0]*24,
    "price_error_bc":[0.0]*24,"load_error_bc":[0.0]*24,
    "wind_on_error_bc":[0.0]*24,"wind_off_error_bc":[0.0]*24,"pv_error_bc":[0.0]*24
})

def run_one(model,K,scenarios,lam,alpha,loss_reference=None):
    print(f"\nRunning {model} | K={K} | lambda={lam} | alpha={alpha}")
    cfg=json.loads(json.dumps(CONFIG))
    cfg["risk"]["risk_lambda"]=float(lam)
    cfg["risk"]["cvar_alpha"]=float(alpha)
    start=time.perf_counter()
    try:
        res=engine.solve(cfg,BASE,scenarios,risk_lambda=lam,loss_reference=loss_reference)
        elapsed=time.perf_counter()-start
        row={
            "model":model,"K":K,"lambda":lam,"alpha":alpha,
            "status":res.get("status"),"objective":res.get("objective"),
            "expected_profit":res.get("expected_profit"),"cvar95":res.get("cvar95"),
            "risk_adjusted_objective":res.get("risk_adjusted_objective"),
            "worst_case_profit":res.get("worst_case_profit"),
            "best_case_profit":res.get("best_case_profit"),
            "runtime_seconds":elapsed,"variables":res.get("variables"),
            "run_status":res.get("run_status"),
        }
        print(row)
        if row["status"] and "Optimal" not in str(row["status"]) and "Feasible" not in str(row["status"]):
            raise RuntimeError(f"Non-feasible solver status: {row['status']}")
        RESULTS.append(row)
        SOLUTIONS[(model,K)]=res
        return row
    except Exception as e:
        row={"model":model,"K":K,"lambda":lam,"alpha":alpha,"status":"FAILED",
             "objective":np.nan,"expected_profit":np.nan,"cvar95":np.nan,
             "risk_adjusted_objective":np.nan,"worst_case_profit":np.nan,
             "best_case_profit":np.nan,"runtime_seconds":time.perf_counter()-start,
             "variables":np.nan,"run_status":repr(e)}
        print(row)
        traceback.print_exc()
        RESULTS.append(row)
        return row

b0=run_one("B0",1,zero,0.0,0.95,loss_reference=0.0)
if not np.isfinite(b0["expected_profit"]):
    print("BLOCKED: B0 did not produce a valid reference profit."); sys.exit(6)

B0_REFERENCE_PROFIT=float(b0["expected_profit"])
print("\nB0 reference profit =",B0_REFERENCE_PROFIT)

for K,path in sorted(SCENARIO_FILES.items()):
    scenarios=load_scenario(path,K)
    run_one("B2",K,scenarios,0.0,0.95,loss_reference=B0_REFERENCE_PROFIT)
    run_one("P1",K,scenarios,0.02,0.95,loss_reference=B0_REFERENCE_PROFIT)

RESULT_DF=pd.DataFrame(RESULTS)
RESULT_DF.to_csv(OUT/"Gate10_Optimization_Results.csv",index=False)

# Scenario diagnostics
scenario_rows=[]
for K,path in sorted(SCENARIO_FILES.items()):
    d=load_scenario(path,K)
    scenario_rows.append({
        "K":K,"unique_scenarios":d.scenario_id.nunique(),"rows":len(d),
        "probability_sum":d[["scenario_id","probability"]].drop_duplicates().probability.sum(),
        "hours_per_scenario":d.groupby("scenario_id").size().mean(),
        "mean_abs_price_error":d.price_error_bc.abs().mean(),
        "mean_abs_load_error":d.load_error_bc.abs().mean(),
        "mean_abs_pv_error":d.pv_error_bc.abs().mean()
    })
SCEN_DF=pd.DataFrame(scenario_rows)
SCEN_DF.to_csv(OUT/"Scenario_Diagnostics.csv",index=False)

# Base table
BASE_TABLE=BASE.copy()
BASE_TABLE.insert(0,"hour_index",np.arange(1,25))
BASE_TABLE.to_csv(OUT/"Base_24h_Forecast.csv",index=False)

# Scenario statistics
long=[]
for K,path in sorted(SCENARIO_FILES.items()):
    d=load_scenario(path,K)
    for col in ["price_error_bc","load_error_bc","wind_on_error_bc","wind_off_error_bc","pv_error_bc"]:
        x=pd.to_numeric(d[col],errors="coerce")
        long.append({"K":K,"variable":col.replace("_error_bc",""),
                     "mean":x.mean(),"std":x.std(ddof=1),
                     "p01":x.quantile(.01),"p05":x.quantile(.05),
                     "median":x.quantile(.50),"p95":x.quantile(.95),
                     "p99":x.quantile(.99),"mae":x.abs().mean(),
                     "min":x.min(),"max":x.max()})
SCEN_STAT_DF=pd.DataFrame(long)
SCEN_STAT_DF.to_csv(OUT/"Scenario_Error_Statistics.csv",index=False)

OPT_SUMMARY=(RESULT_DF.groupby(["model","K"],as_index=False)
             .agg(expected_profit=("expected_profit","first"),
                  cvar95=("cvar95","first"),
                  risk_adjusted_objective=("risk_adjusted_objective","first"),
                  worst_case_profit=("worst_case_profit","first"),
                  best_case_profit=("best_case_profit","first"),
                  runtime_seconds=("runtime_seconds","first"),
                  status=("status","first"),variables=("variables","first")))
OPT_SUMMARY.to_csv(OUT/"Optimization_Summary.csv",index=False)

def savefig(path):
    plt.tight_layout(); plt.savefig(path,dpi=400,bbox_inches="tight"); plt.close()

# Distribution figures
for var in ["price","load","wind_on","wind_off","pv"]:
    plt.figure(figsize=(7.2,4.5))
    for K,path in sorted(SCENARIO_FILES.items()):
        d=load_scenario(path,K)
        x=pd.to_numeric(d[f"{var}_error_bc"],errors="coerce").dropna().to_numpy()
        if len(x)>2 and np.std(x)>0:
            grid=np.linspace(np.quantile(x,.005),np.quantile(x,.995),250)
            kde=gaussian_kde(x)
            plt.plot(grid,kde(grid),label=f"K={K}")
    plt.xlabel(f"{var.replace('_',' ').title()} calibrated error")
    plt.ylabel("Density"); plt.title(f"Calibrated {var.replace('_',' ').title()} Error Distribution")
    plt.legend(frameon=False); plt.grid(alpha=.2); savefig(OUT/f"Fig_{var}_error_distribution.png")

# Runtime / objective / profit / CVaR
for y,title,ylabel,name in [
    ("runtime_seconds","Computational Performance","MILP runtime (s)","Fig_Runtime_vs_K.png"),
    ("objective","Risk-adjusted Objective Stability Under Scenario Reduction","Risk-adjusted objective","Fig_Objective_vs_K.png"),
    ("expected_profit","Expected Profit Under Scenario Reduction","Expected profit (EUR)","Fig_Expected_Profit_vs_K.png"),
    ("cvar95","Tail Risk Under Scenario Reduction","CVaR95 loss (EUR)","Fig_CVaR95_vs_K.png")
]:
    plt.figure(figsize=(7.2,4.5))
    for model in RESULT_DF.model.dropna().unique():
        x=RESULT_DF[RESULT_DF.model==model].sort_values("K")
        plt.plot(x.K,x[y],marker="o",linewidth=1.8,label=model)
    plt.xlabel("Number of reduced scenarios, K"); plt.ylabel(ylabel); plt.title(title)
    plt.legend(frameon=False); plt.grid(alpha=.2); savefig(OUT/name)

# Scenario diagnostics
plt.figure(figsize=(7.2,4.5))
for col,label in [("mean_abs_price_error","Price"),("mean_abs_load_error","Load"),("mean_abs_pv_error","PV")]:
    plt.plot(SCEN_DF.K,SCEN_DF[col],marker="o",linewidth=1.7,label=label)
plt.xlabel("Number of reduced scenarios, K"); plt.ylabel("Mean absolute calibrated error")
plt.title("Scenario-Set Quality"); plt.legend(frameon=False); plt.grid(alpha=.2)
savefig(OUT/"Fig_Scenario_Diagnostics.png")

# Excel
xlsx=OUT/"Gate10_REAL_RESULTS.xlsx"
def excel_safe(df):
    x=df.copy()
    for c in x.columns:
        if isinstance(x[c].dtype,pd.DatetimeTZDtype):
            x[c]=x[c].dt.tz_localize(None)
    return x

with pd.ExcelWriter(xlsx,engine="openpyxl") as writer:
    excel_safe(RESULT_DF).to_excel(writer,"Optimization",index=False)
    excel_safe(SCEN_DF).to_excel(writer,"Scenario_Diagnostics",index=False)
    excel_safe(BASE_TABLE).to_excel(writer,"Base_24h",index=False)
    excel_safe(SCEN_STAT_DF).to_excel(writer,"Scenario_Statistics",index=False)
    excel_safe(OPT_SUMMARY).to_excel(writer,"Optimization_Summary",index=False)

report={"gate":"10F-10J","timestamp":pd.Timestamp.utcnow().isoformat(),
        "optimization_results":RESULT_DF.to_dict("records"),
        "scenario_diagnostics":SCEN_DF.to_dict("records"),
        "B0_reference_profit":B0_REFERENCE_PROFIT,
        "config_file":str(FILES["config"]),
        "config_status":"external_locked_config" if FILES["config"] else "PROVISIONAL_FALLBACK"}

with open(OUT/"Gate10_RUN_REPORT.json","w",encoding="utf-8") as f:
    json.dump(report,f,indent=2,ensure_ascii=False,default=str)

print("\n"+"="*70)
print("GATE 10 EXECUTION FINISHED")
print("="*70)
print(RESULT_DF.to_string(index=False))
print("\nOUTPUT:",OUT)
for p in sorted(OUT.iterdir()): print(" ",p.name)

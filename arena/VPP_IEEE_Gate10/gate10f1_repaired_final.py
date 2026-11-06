from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, List
import json, math, time
import numpy as np
import pandas as pd
import highspy

HOURS = 24
STAGES = 7
SCENARIO_SETS = (30, 50, 100)
SCENARIO_COLUMNS = ["scenario_id","hour","probability","price_error_bc","load_error_bc","wind_on_error_bc","wind_off_error_bc","pv_error_bc"]

@dataclass(frozen=True)
class Group:
    name: str; dg_mw: float; dr_mw: float; import_mw: float; export_mw: float; renewable_mw: float

@dataclass(frozen=True)
class Battery:
    energy_mwh: float; charge_mw: float; discharge_mw: float; initial_soc_mwh: float
    min_soc_fraction: float; max_soc_fraction: float; eta_charge: float; eta_discharge: float
    degradation_cost_eur_mwh: float

class VR:
    def __init__(self): self.v = {}
    def add(self,k,v):
        if k in self.v: raise KeyError(k)
        self.v[k]=v
    def __getitem__(self,k): return self.v[k]
    def __len__(self): return len(self.v)

def validate_config(c):
    if c.get("horizon_hours") != HOURS or c.get("operational_stages") != STAGES:
        raise ValueError("Final model requires 24 hours and 7 operational stages.")
    stages=c.get("stages")
    if not isinstance(stages,list) or len(stages)!=STAGES:
        raise ValueError("Exactly seven stages are required.")
    ids=[int(s["stage_id"]) for s in stages]
    if ids != list(range(1,STAGES+1)): raise ValueError("stage_id must be 1..7.")
    first=[int(s["first_available_hour"]) for s in stages]
    if any(h<0 or h>=HOURS for h in first): raise ValueError("Stage gate hours must be in 0..23.")
    if first != sorted(first): raise ValueError("Stage gates must be chronological.")
    if len(set(first))==1 and first[0]==0:
        raise ValueError("Template chronology is not acceptable: all seven gates are at hour 0. Supply the locked market-gate timing.")
    if not c.get("dispatch_groups"): raise ValueError("Final dispatch-group definitions are required.")
    for g in c["dispatch_groups"]:
        for k in ["name","dg_mw","dr_mw","import_mw","export_mw","renewable_mw"]:
            if g.get(k) is None: raise ValueError(f"Missing dispatch-group parameter: {k}")
    if "battery" not in c: raise ValueError("Battery configuration missing.")
    if "market" not in c: raise ValueError("Market configuration missing.")
    for k in ["reserve_price_eur_per_mw","intraday_price_spread_eur_mwh","dr_price_eur_per_mwh","grid_import_price_eur_mwh","grid_export_price_eur_mwh","unserved_energy_penalty_eur_mwh"]:
        if c["market"].get(k) is None: raise ValueError(f"Missing market parameter: {k}")
    if "renewable_mapping_factor" not in c:
        raise ValueError("renewable_mapping_factor is required; do not multiply German system forecasts by VPP capacity implicitly.")
    if "load_mapping_factor" not in c:
        raise ValueError("load_mapping_factor is required; system load must be explicitly mapped to the VPP scale.")
    if float(c["renewable_mapping_factor"]) <= 0 or float(c["load_mapping_factor"]) <= 0:
        raise ValueError("renewable_mapping_factor and load_mapping_factor must be positive.")
    risk=c.get("risk",{})
    alpha=float(risk.get("cvar_alpha",0.95))
    lam=float(risk.get("risk_lambda",0.0))
    if not 0<alpha<1: raise ValueError("cvar_alpha must be in (0,1).")
    if lam<0: raise ValueError("risk_lambda must be nonnegative.")

def groups(c): return [Group(str(g["name"]),float(g["dg_mw"]),float(g["dr_mw"]),float(g["import_mw"]),float(g["export_mw"]),float(g["renewable_mw"])) for g in c["dispatch_groups"]]
def battery(c):
    b=c["battery"]; return Battery(float(b["energy_mwh"]),float(b["charge_mw"]),float(b["discharge_mw"]),float(b["initial_soc_mwh"]),float(b["min_soc_fraction"]),float(b["max_soc_fraction"]),float(b["eta_charge"]),float(b["eta_discharge"]),float(b["degradation_cost_eur_mwh"]))

def load_scenarios(path,k):
    df=pd.read_csv(path)
    miss=[x for x in SCENARIO_COLUMNS if x not in df.columns]
    if miss: raise ValueError(f"Missing scenario columns: {miss}")
    df=df.sort_values(["scenario_id","hour"]).reset_index(drop=True)
    if df.scenario_id.nunique()!=k: raise ValueError(f"Expected K={k}.")
    lens=df.groupby("scenario_id").size()
    if not (lens==HOURS).all(): raise ValueError("Every scenario must contain 24 hours.")
    p=df[["scenario_id","probability"]].drop_duplicates()
    if not np.isclose(p.probability.sum(),1.0,atol=1e-10): raise ValueError("Scenario probabilities must sum to 1.")
    return df

def build_model(config, base, scenarios, risk_lambda=None, alpha=None):
    G=groups(config); B=battery(config); M=config["market"]; risk=config.get("risk",{})
    lam=float(risk.get("risk_lambda",0.0) if risk_lambda is None else risk_lambda)
    alpha=float(risk.get("cvar_alpha",0.95) if alpha is None else alpha)
    sids=sorted(scenarios.scenario_id.unique())
    prob=scenarios[["scenario_id","probability"]].drop_duplicates().set_index("scenario_id").probability.to_dict()
    h=highspy.Highs(); h.setOptionValue("time_limit",float(config.get("solver",{}).get("time_limit_seconds",300))); h.setOptionValue("mip_rel_gap",float(config.get("solver",{}).get("mip_rel_gap",0.01)))
    v=VR()
    # First-stage / commitment variables
    for t in range(HOURS):
        v.add(("DA",t),h.addVariable(lb=0,ub=1e6,name=f"DA_{t}"))
        v.add(("IDSELL",t),h.addVariable(lb=0,ub=1e6,name=f"IDSELL_{t}"))
        v.add(("IDBUY",t),h.addVariable(lb=0,ub=1e6,name=f"IDBUY_{t}"))
        v.add(("DRU",t),h.addVariable(lb=0,ub=1e6,name=f"DRU_{t}")); v.add(("DRD",t),h.addVariable(lb=0,ub=1e6,name=f"DRD_{t}"))
        v.add(("DG",t),h.addVariable(lb=0,ub=sum(g.dg_mw for g in G),name=f"DG_{t}"))
        v.add(("CH",t),h.addVariable(lb=0,ub=B.charge_mw,name=f"CH_{t}")); v.add(("DCH",t),h.addVariable(lb=0,ub=B.discharge_mw,name=f"DCH_{t}"))
        v.add(("SOC",t),h.addVariable(lb=B.energy_mwh*B.min_soc_fraction,ub=B.energy_mwh*B.max_soc_fraction,name=f"SOC_{t}"))
        v.add(("UCH",t),h.addVariable(lb=0,ub=1,type=highspy.HighsVarType.kInteger,name=f"UCH_{t}"))
        v.add(("RES",t),h.addVariable(lb=0,ub=1e6,name=f"RES_{t}"))
        v.add(("CUM",1,t),h.addVariable(lb=0,ub=1e6,name=f"CUM_1_{t}"))
        for st in range(2,STAGES+1): v.add(("CUM",st,t),h.addVariable(lb=0,ub=1e6,name=f"CUM_{st}_{t}"))
    for sid in sids:
        for t in range(HOURS):
            v.add(("RTSELL",sid,t),h.addVariable(lb=0,ub=1e6,name=f"RTSELL_{sid}_{t}")); v.add(("RTBUY",sid,t),h.addVariable(lb=0,ub=1e6,name=f"RTBUY_{sid}_{t}"))
            v.add(("RTMODE",sid,t),h.addVariable(lb=0,ub=1,type=highspy.HighsVarType.kInteger,name=f"RTMODE_{sid}_{t}"))
            v.add(("RACT",sid,t),h.addVariable(lb=0,ub=1e6,name=f"RACT_{sid}_{t}")); v.add(("UNS",sid,t),h.addVariable(lb=0,ub=1e6,name=f"UNS_{sid}_{t}"))
        v.add(("PROFIT",sid),h.addVariable(lb=-1e12,ub=1e12,name=f"PROFIT_{sid}")); v.add(("LOSS",sid),h.addVariable(lb=-1e12,ub=1e12,name=f"LOSS_{sid}")); v.add(("XI",sid),h.addVariable(lb=0,ub=1e12,name=f"XI_{sid}"))
    v.add(("ETA",),h.addVariable(lb=-1e12,ub=1e12,name="ETA"))
    # First-stage forecast balance. Renewable mapping factor is explicit and auditable.
    rf=float(config["renewable_mapping_factor"])
    lf=float(config["load_mapping_factor"])
    import_cap=sum(g.import_mw for g in G)
    export_cap=sum(g.export_mw for g in G)
    for t in range(HOURS):
        load=float(base.loc[t,"load_forecast"])*lf
        ren=max(0,float(base.loc[t,"wind_on_forecast"]))+max(0,float(base.loc[t,"wind_off_forecast"]))+max(0,float(base.loc[t,"pv_forecast"]))
        ren=min(ren*rf, sum(g.renewable_mw for g in G))
        h.addConstr(ren+v[("DG",t)]+v[("DCH",t)]+v[("IDBUY",t)]+v[("DRU",t)] >= load+v[("CH",t)]+v[("DA",t)]+v[("IDSELL",t)])
        h.addConstr(v[("IDBUY",t)] <= import_cap)
        h.addConstr(v[("DA",t)] + v[("IDSELL",t)] <= export_cap)
        h.addConstr(v[("DRU",t)]<=sum(g.dr_mw for g in G)); h.addConstr(v[("DRD",t)]<=sum(g.dr_mw for g in G))
        h.addConstr(v[("CH",t)]<=B.charge_mw*v[("UCH",t)]); h.addConstr(v[("DCH",t)]<=B.discharge_mw*(1-v[("UCH",t)]))
        prev=B.initial_soc_mwh if t==0 else v[("SOC",t-1)]
        h.addConstr(v[("SOC",t)]==prev+B.eta_charge*v[("CH",t)]-v[("DCH",t)]/B.eta_discharge)
    h.addConstr(v[("SOC",HOURS-1)]==B.initial_soc_mwh)
    h.addConstr(sum(v[("DRU",t)] for t in range(HOURS))==sum(v[("DRD",t)] for t in range(HOURS)))
    # Chronological cumulative commitment.
    gates={int(s["stage_id"]):int(s["first_available_hour"]) for s in config["stages"]}
    flex_cap=sum(g.dg_mw+g.dr_mw for g in G)+B.discharge_mw
    for st in range(1,STAGES+1):
        for t in range(HOURS):
            prior=0 if st==1 else v[("CUM",st-1,t)]
            if t<gates[st]: h.addConstr(v[("CUM",st,t)]==prior)
            else:
                add=v[("RES",t)]+v[("IDSELL",t)] if st==1 else v[("IDSELL",t)]
                h.addConstr(v[("CUM",st,t)]==prior+add)
            h.addConstr(v[("CUM",st,t)]<=flex_cap)
    # Scenario recourse and profit definition.
    for sid in sids:
        block=scenarios[scenarios.scenario_id==sid].sort_values("hour").reset_index(drop=True)
        profit_terms=[]
        for t in range(HOURS):
            r=block.iloc[t]; load=(float(base.loc[t,"load_forecast"])+float(r.load_error_bc))*lf
            ren_raw=(max(0,float(base.loc[t,"wind_on_forecast"])+float(r.wind_on_error_bc))+max(0,float(base.loc[t,"wind_off_forecast"])+float(r.wind_off_error_bc))+max(0,float(base.loc[t,"pv_forecast"])+float(r.pv_error_bc)))
            ren=min(ren_raw*rf, sum(g.renewable_mw for g in G))
            rt_price=float(base.loc[t,"forecast_hybrid"])+float(r.price_error_bc)
            # Preserve negative prices; no clipping.
            h.addConstr(v[("RACT",sid,t)]<=v[("RES",t)])
            h.addConstr(v[("RTSELL",sid,t)]<=export_cap*v[("RTMODE",sid,t)])
            h.addConstr(v[("RTBUY",sid,t)]<=import_cap*(1-v[("RTMODE",sid,t)]))
            h.addConstr(ren+v[("DG",t)]+v[("DCH",t)]+v[("RTBUY",sid,t)]+v[("DRU",t)]+v[("RACT",sid,t)]+v[("UNS",sid,t)] >= load+v[("CH",t)]+v[("RTSELL",sid,t)])
            da=float(base.loc[t,"forecast_hybrid"]); ids=float(M["intraday_price_spread_eur_mwh"]); rp=float(M["reserve_price_eur_per_mw"]); drp=float(M["dr_price_eur_per_mwh"]); dgc=float(M.get("dg_cost_eur_mwh",0)); pen=float(M["unserved_energy_penalty_eur_mwh"])
            profit_terms += [
                da*v[("DA",t)],
                (da-ids)*v[("IDSELL",t)],
                -(da+ids)*v[("IDBUY",t)],
                rp*v[("RES",t)],
                drp*(v[("DRU",t)]-v[("DRD",t)]),
                -dgc*v[("DG",t)],
                -B.degradation_cost_eur_mwh*(v[("CH",t)]+v[("DCH",t)]),
                rt_price*v[("RTSELL",sid,t)],
                -rt_price*v[("RTBUY",sid,t)],
                -pen*v[("UNS",sid,t)]
            ]
        h.addConstr(v[("PROFIT",sid)]==sum(profit_terms)); h.addConstr(v[("LOSS",sid)]==-v[("PROFIT",sid)])
        h.addConstr(v[("XI",sid)]>=v[("LOSS",sid)]-v[("ETA",)])
    # N-1 group-level surviving flexible capability (locked Gate 10F1R formulation).
    if config.get("reliability",{}).get("n_minus_1_required",True):
        for outage in range(len(G)):
            cap=sum(g.dg_mw+g.dr_mw for i,g in enumerate(G) if i!=outage)+B.discharge_mw
            for t in range(HOURS): h.addConstr(v[("RES",t)]<=cap)
    # Risk-adjusted objective: expected profit - lambda * CVaR(loss).
    expected=sum(float(prob[s])*v[("PROFIT",s)] for s in sids)
    cvar=v[("ETA",)]+sum(float(prob[s])*v[("XI",s)] for s in sids)/(1-alpha)
    h.maximize(expected-lam*cvar)
    return h,v,prob

def solve(config,base,scenarios,risk_lambda=None):
    start=time.perf_counter()
    m,v,prob=build_model(config,base,scenarios,risk_lambda=risk_lambda)
    run=m.run()
    elapsed=time.perf_counter()-start
    status=str(m.getModelStatus())
    ok=("Optimal" in status or "Feasible" in status)
    if not ok:
        return {"status":status,"objective":math.nan,"expected_profit":math.nan,"cvar95":math.nan,"risk_adjusted_objective":math.nan,"worst_case_profit":math.nan,"best_case_profit":math.nan,"runtime_seconds":elapsed,"variables":len(v),"run_status":str(run)}
    sol=m.getSolution()
    profits={}
    for sid in prob:
        profits[sid]=float(sol.col_value[v[("PROFIT",sid)]])
    expected_profit=float(sum(float(prob[s])*profits[s] for s in prob))
    # Direct weighted empirical CVaR of LOSS = -PROFIT; this is independent of ETA/XI.
    losses=np.array([-profits[s] for s in prob],dtype=float)
    ps=np.array([float(prob[s]) for s in prob],dtype=float)
    order=np.argsort(losses)[::-1]
    losses=losses[order]; ps=ps[order]
    alpha=float(config.get("risk",{}).get("cvar_alpha",0.95))
    tail=1.0-alpha; mass=0.0; cvar=0.0
    for L,p in zip(losses,ps):
        take=min(p,tail-mass)
        if take>0:
            cvar += take*L; mass += take
        if mass >= tail-1e-12: break
    cvar95=float(cvar/tail) if tail>0 else math.nan
    objective=float(m.getObjectiveValue())
    decisions={k:[] for k in ["DA","IDSELL","IDBUY","DRU","DRD","DG","CH","DCH","SOC","RES"]}
    for t in range(HOURS):
        for k in decisions:
            decisions[k].append(float(sol.col_value[v[(k,t)]]))
    return {"status":status,"objective":objective,"expected_profit":expected_profit,"cvar95":cvar95,"risk_adjusted_objective":expected_profit-float(risk_lambda if risk_lambda is not None else config.get("risk",{}).get("risk_lambda",0.0))*cvar95,"worst_case_profit":float(min(profits.values())),"best_case_profit":float(max(profits.values())),"scenario_profits":profits,"decisions":decisions,"runtime_seconds":elapsed,"variables":len(v),"run_status":str(run)}

if __name__=='__main__':
    print('Gate 10F.1 repaired engine: empirical execution requires validated Gate-10 inputs and final configuration.')

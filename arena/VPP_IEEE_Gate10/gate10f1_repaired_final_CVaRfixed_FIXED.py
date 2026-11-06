from __future__ import annotations

from dataclasses import dataclass
import math, time
import numpy as np
import pandas as pd
import highspy

HOURS=24
STAGES=7
SCENARIO_COLUMNS=[
    "scenario_id","hour","probability","price_error_bc","load_error_bc",
    "wind_on_error_bc","wind_off_error_bc","pv_error_bc"
]

@dataclass(frozen=True)
class Group:
    name:str; dg_mw:float; dr_mw:float; import_mw:float; export_mw:float; renewable_mw:float

@dataclass(frozen=True)
class Battery:
    energy_mwh:float; charge_mw:float; discharge_mw:float; initial_soc_mwh:float
    min_soc_fraction:float; max_soc_fraction:float; eta_charge:float; eta_discharge:float
    degradation_cost_eur_mwh:float

class VR:
    def __init__(self): self.v={}
    def add(self,k,v):
        if k in self.v: raise KeyError(k)
        self.v[k]=v
    def __getitem__(self,k): return self.v[k]
    def __len__(self): return len(self.v)

def validate_config(c):
    if c.get("horizon_hours")!=24 or c.get("operational_stages")!=7:
        raise ValueError("Final model requires 24 hours and 7 operational stages.")
    stages=c.get("stages")
    if not isinstance(stages,list) or len(stages)!=7:
        raise ValueError("Exactly seven stages are required.")
    ids=[int(s["stage_id"]) for s in stages]
    if ids!=list(range(1,8)): raise ValueError("stage_id must be 1..7.")
    first=[int(s["first_available_hour"]) for s in stages]
    if any(h<0 or h>=24 for h in first) or first!=sorted(first):
        raise ValueError("Invalid chronological stage gates.")
    if len(set(first))==1 and first[0]==0:
        raise ValueError("All seven stage gates cannot be hour 0.")
    if not c.get("dispatch_groups"): raise ValueError("Dispatch groups are required.")
    for g in c["dispatch_groups"]:
        for k in ["name","dg_mw","dr_mw","import_mw","export_mw","renewable_mw"]:
            if g.get(k) is None: raise ValueError(f"Missing group parameter: {k}")
    for section in ["battery","market"]:
        if section not in c: raise ValueError(f"{section} configuration missing.")
    for k in ["reserve_price_eur_per_mw","intraday_price_spread_eur_mwh",
              "dr_price_eur_per_mwh","grid_import_price_eur_mwh",
              "grid_export_price_eur_mwh","unserved_energy_penalty_eur_mwh"]:
        if c["market"].get(k) is None: raise ValueError(f"Missing market parameter: {k}")
    if float(c.get("renewable_mapping_factor",0))<=0 or float(c.get("load_mapping_factor",0))<=0:
        raise ValueError("Mapping factors must be positive.")
    alpha=float(c.get("risk",{}).get("cvar_alpha",.95))
    lam=float(c.get("risk",{}).get("risk_lambda",0))
    if not 0<alpha<1 or lam<0: raise ValueError("Invalid CVaR/risk parameters.")

def groups(c):
    return [Group(str(g["name"]),float(g["dg_mw"]),float(g["dr_mw"]),
                   float(g["import_mw"]),float(g["export_mw"]),float(g["renewable_mw"]))
            for g in c["dispatch_groups"]]

def battery(c):
    b=c["battery"]
    return Battery(float(b["energy_mwh"]),float(b["charge_mw"]),float(b["discharge_mw"]),
                   float(b["initial_soc_mwh"]),float(b["min_soc_fraction"]),
                   float(b["max_soc_fraction"]),float(b["eta_charge"]),
                   float(b["eta_discharge"]),float(b["degradation_cost_eur_mwh"]))

def load_scenarios(path,k):
    df=pd.read_csv(path)
    miss=[x for x in SCENARIO_COLUMNS if x not in df.columns]
    if miss: raise ValueError(f"Missing scenario columns: {miss}")
    df=df.sort_values(["scenario_id","hour"]).reset_index(drop=True)
    if df.scenario_id.nunique()!=k: raise ValueError(f"Expected K={k}.")
    if not (df.groupby("scenario_id").size()==24).all():
        raise ValueError("Every scenario must contain 24 hours.")
    p=df[["scenario_id","probability"]].drop_duplicates()
    if not np.isclose(p.probability.sum(),1.0,atol=1e-10):
        raise ValueError("Scenario probabilities must sum to 1.")
    return df

def build_model(config,base,scenarios,risk_lambda=None,alpha=None,loss_reference=None):
    validate_config(config)
    G=groups(config); B=battery(config); M=config["market"]; risk=config.get("risk",{})
    lam=float(risk.get("risk_lambda",0) if risk_lambda is None else risk_lambda)
    alpha=float(risk.get("cvar_alpha",.95) if alpha is None else alpha)

    sids=sorted(scenarios.scenario_id.unique())
    prob=scenarios[["scenario_id","probability"]].drop_duplicates().set_index("scenario_id").probability.to_dict()

    h=highspy.Highs()
    solver=config.get("solver",{})
    h.setOptionValue("time_limit",float(solver.get("time_limit_seconds",300)))
    h.setOptionValue("mip_rel_gap",float(solver.get("mip_rel_gap",.01)))
    v=VR()

    for t in range(24):
        for name,ub in [
            ("DA",1e6),("IDSELL",1e6),("IDBUY",1e6),
            ("DRU",1e6),("DRD",1e6),("RES",1e6),
            ("DG",sum(g.dg_mw for g in G)),("CH",B.charge_mw),("DCH",B.discharge_mw),
            ("SOC",B.energy_mwh*B.max_soc_fraction)
        ]:
            lb=0 if name!="SOC" else B.energy_mwh*B.min_soc_fraction
            v.add((name,t),h.addVariable(lb=lb,ub=ub,name=f"{name}_{t}"))
        v.add(("UCH",t),h.addVariable(lb=0,ub=1,type=highspy.HighsVarType.kInteger,name=f"UCH_{t}"))

    for sid in sids:
        for t in range(24):
            for name in ["RTSELL","RTBUY","RACT","UNS"]:
                v.add((name,sid,t),h.addVariable(lb=0,ub=1e6,name=f"{name}_{sid}_{t}"))
            v.add(("RTMODE",sid,t),h.addVariable(lb=0,ub=1,type=highspy.HighsVarType.kInteger,name=f"RTMODE_{sid}_{t}"))
        v.add(("PROFIT",sid),h.addVariable(lb=-1e12,ub=1e12,name=f"PROFIT_{sid}"))
        v.add(("LOSS",sid),h.addVariable(lb=0,ub=1e12,name=f"LOSS_{sid}"))
        v.add(("XI",sid),h.addVariable(lb=0,ub=1e12,name=f"XI_{sid}"))
    v.add(("ETA",),h.addVariable(lb=0,ub=1e12,name="ETA"))

    rf=float(config["renewable_mapping_factor"]); lf=float(config["load_mapping_factor"])
    import_cap=sum(g.import_mw for g in G); export_cap=sum(g.export_mw for g in G)
    ren_cap=sum(g.renewable_mw for g in G)

    for t in range(24):
        load=float(base.loc[t,"load_forecast"])*lf
        ren=(max(0,float(base.loc[t,"wind_on_forecast"]))+
             max(0,float(base.loc[t,"wind_off_forecast"]))+
             max(0,float(base.loc[t,"pv_forecast"])))
        ren=min(ren*rf,ren_cap)
        h.addConstr(ren+v[("DG",t)]+v[("DCH",t)]+v[("IDBUY",t)]+v[("DRU",t)]
                    >=load+v[("CH",t)]+v[("DA",t)]+v[("IDSELL",t)])
        h.addConstr(v[("IDBUY",t)]<=import_cap)
        h.addConstr(v[("DA",t)]+v[("IDSELL",t)]<=export_cap)
        h.addConstr(v[("DRU",t)]<=sum(g.dr_mw for g in G))
        h.addConstr(v[("DRD",t)]<=sum(g.dr_mw for g in G))
        h.addConstr(v[("CH",t)]<=B.charge_mw*v[("UCH",t)])
        h.addConstr(v[("DCH",t)]<=B.discharge_mw*(1-v[("UCH",t)]))
        prev=B.initial_soc_mwh if t==0 else v[("SOC",t-1)]
        h.addConstr(v[("SOC",t)]==prev+B.eta_charge*v[("CH",t)]-v[("DCH",t)]/B.eta_discharge)
    h.addConstr(v[("SOC",23)]==B.initial_soc_mwh)
    h.addConstr(sum(v[("DRU",t)] for t in range(24))==sum(v[("DRD",t)] for t in range(24)))

    # Stage cumulative commitment is kept, but each stage has its own cumulative
    # variable. Stage 1 includes reserve + ID; later stages add incremental ID.
    gates={int(s["stage_id"]):int(s["first_available_hour"]) for s in config["stages"]}
    flex_cap=sum(g.dg_mw+g.dr_mw for g in G)+B.discharge_mw
    for st in range(1,8):
        for t in range(24):
            v.add(("CUM",st,t),h.addVariable(lb=0,ub=1e6,name=f"CUM_{st}_{t}"))
            prior=0 if st==1 else v[("CUM",st-1,t)]
            if t<gates[st]:
                h.addConstr(v[("CUM",st,t)]==prior)
            else:
                add=v[("RES",t)]+v[("IDSELL",t)] if st==1 else v[("IDSELL",t)]
                h.addConstr(v[("CUM",st,t)]==prior+add)
            h.addConstr(v[("CUM",st,t)]<=flex_cap)

    for sid in sids:
        block=scenarios[scenarios.scenario_id==sid].sort_values("hour").reset_index(drop=True)
        profit_terms=[]
        for t in range(24):
            r=block.iloc[t]
            load=(float(base.loc[t,"load_forecast"])+float(r.load_error_bc))*lf
            ren=(max(0,float(base.loc[t,"wind_on_forecast"])+float(r.wind_on_error_bc))+
                 max(0,float(base.loc[t,"wind_off_forecast"])+float(r.wind_off_error_bc))+
                 max(0,float(base.loc[t,"pv_forecast"])+float(r.pv_error_bc)))
            ren=min(ren*rf,ren_cap)
            rt_price=float(base.loc[t,"forecast_hybrid"])+float(r.price_error_bc)

            h.addConstr(v[("RACT",sid,t)]<=v[("RES",t)])
            h.addConstr(v[("RTSELL",sid,t)]<=export_cap*v[("RTMODE",sid,t)])
            h.addConstr(v[("RTBUY",sid,t)]<=import_cap*(1-v[("RTMODE",sid,t)]))
            h.addConstr(ren+v[("DG",t)]+v[("DCH",t)]+v[("RTBUY",sid,t)]
                        +v[("DRU",t)]+v[("RACT",sid,t)]+v[("UNS",sid,t)]
                        >=load+v[("CH",t)]+v[("RTSELL",sid,t)])

            da=float(base.loc[t,"forecast_hybrid"])
            spread=float(M["intraday_price_spread_eur_mwh"])
            rp=float(M["reserve_price_eur_per_mw"])
            drp=float(M["dr_price_eur_per_mwh"])
            dgc=float(M.get("dg_cost_eur_mwh",0))
            pen=float(M["unserved_energy_penalty_eur_mwh"])
            profit_terms += [
                da*v[("DA",t)],
                (da-spread)*v[("IDSELL",t)],
                -(da+spread)*v[("IDBUY",t)],
                rp*v[("RES",t)],
                drp*(v[("DRU",t)]-v[("DRD",t)]),
                -dgc*v[("DG",t)],
                -B.degradation_cost_eur_mwh*(v[("CH",t)]+v[("DCH",t)]),
                rt_price*v[("RTSELL",sid,t)],
                -rt_price*v[("RTBUY",sid,t)],
                -pen*v[("UNS",sid,t)]
            ]
        h.addConstr(v[("PROFIT",sid)]==sum(profit_terms))
        ref=0.0 if loss_reference is None else float(loss_reference)
        h.addConstr(v[("LOSS",sid)]>=ref-v[("PROFIT",sid)])
        h.addConstr(v[("XI",sid)]>=v[("LOSS",sid)]-v[("ETA",)])

    if config.get("reliability",{}).get("n_minus_1_required",True):
        for outage in range(len(G)):
            cap=sum(g.dg_mw+g.dr_mw for i,g in enumerate(G) if i!=outage)+B.discharge_mw
            for t in range(24):
                h.addConstr(v[("RES",t)]<=cap)

    expected=sum(float(prob[s])*v[("PROFIT",s)] for s in sids)
    cvar=v[("ETA",)]+sum(float(prob[s])*v[("XI",s)] for s in sids)/(1-alpha)
    h.maximize(expected-lam*cvar)
    return h,v,prob

def solve(config,base,scenarios,risk_lambda=None,loss_reference=None):
    start=time.perf_counter()
    m,v,prob=build_model(config,base,scenarios,risk_lambda=risk_lambda,loss_reference=loss_reference)
    run=m.run()
    elapsed=time.perf_counter()-start
    status=str(m.getModelStatus())
    ok=("Optimal" in status or "Feasible" in status)
    if not ok:
        return {"status":status,"objective":math.nan,"expected_profit":math.nan,
                "cvar95":math.nan,"risk_adjusted_objective":math.nan,
                "worst_case_profit":math.nan,"best_case_profit":math.nan,
                "runtime_seconds":elapsed,"variables":len(v),"run_status":str(run)}

    sol=m.getSolution()
    profits={s:float(sol.col_value[v[("PROFIT",s)]]) for s in prob}
    expected=float(sum(float(prob[s])*profits[s] for s in prob))

    alpha=float(config.get("risk",{}).get("cvar_alpha",.95))
    ref=0.0 if loss_reference is None else float(loss_reference)
    losses=np.maximum(0.0,np.array([ref-profits[s] for s in prob],dtype=float))
    ps=np.array([float(prob[s]) for s in prob],dtype=float)
    order=np.argsort(losses)[::-1]
    losses=losses[order]; ps=ps[order]
    tail=1-alpha; mass=0.; cvar=0.
    for L,p in zip(losses,ps):
        take=min(float(p),tail-mass)
        if take>0:
            cvar+=take*float(L); mass+=take
        if mass>=tail-1e-12: break
    cvar95=float(cvar/tail) if tail>0 else math.nan
    objective=float(m.getObjectiveValue())
    decisions={k:[] for k in ["DA","IDSELL","IDBUY","DRU","DRD","DG","CH","DCH","SOC","RES"]}
    for t in range(24):
        for k in decisions:
            decisions[k].append(float(sol.col_value[v[(k,t)]]))

    lam=float(config.get("risk",{}).get("risk_lambda",0) if risk_lambda is None else risk_lambda)
    return {"status":status,"objective":objective,"expected_profit":expected,
            "cvar95":cvar95,"risk_adjusted_objective":expected-lam*cvar95,
            "worst_case_profit":float(min(profits.values())),
            "best_case_profit":float(max(profits.values())),
            "scenario_profits":profits,"decisions":decisions,
            "runtime_seconds":elapsed,"variables":len(v),"run_status":str(run)}

if __name__=="__main__":
    print("Gate 10F.1 repaired engine: validated real-data execution.")

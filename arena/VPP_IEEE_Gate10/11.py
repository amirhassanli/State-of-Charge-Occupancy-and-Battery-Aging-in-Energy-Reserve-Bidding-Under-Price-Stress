import numpy as np
import pandas as pd
import highspy
import json
import time
from pathlib import Path

# ============================================================
# PATHS & CONFIG
# ============================================================
ROOT = Path(__file__).resolve().parent
SCENARIO_DIR = ROOT / "data" / "scenarios" / "reduced_scenarios"
RESULTS_DIR = ROOT / "results" / "alocabid_highspy_fixed"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# --- Physical Parameters ---
P_MAX = 150.0
P_DG_MIN = 0.0
P_DG_MAX = 30.0
DG_COST = 45.0

E_INIT = 2.0
E_MIN = 2.0
E_MAX = 20.0
P_CH_MAX = 5.0
P_DIS_MAX = 5.0
ETA_CH = 0.95
ETA_DIS = 0.95
DEG_COST = 2.5

DR_PLUS_MAX = 10.0
DR_MINUS_MAX = 10.0
DR_COST = 20.0

C_IMB_PLUS = 1.2
C_IMB_MINUS = 1.2

ALPHA = 0.95
LAMBDA_RISK = 0.8

M_BIG = 1e6  # Big-M for binary constraints

# ============================================================
# LOAD SCENARIOS
# ============================================================
def load_reduced_scenarios(K):
    file = SCENARIO_DIR / f"scenario_reduced_{K}.csv"
    if not file.exists():
        raise FileNotFoundError(f"Missing: {file}")
    df = pd.read_csv(file)
    required = ["scenario_id", "hour", "probability", 
                "price_error_bc", "load_error_bc", 
                "wind_on_error_bc", "wind_off_error_bc", "pv_error_bc"]
    if not all(c in df.columns for c in required):
        raise ValueError(f"Missing columns in {file}")
    return df.sort_values(["scenario_id", "hour"]).reset_index(drop=True)

# ============================================================
# BUILD HIGHSPY MODEL (WITH CORRECT BALANCE CONSTRAINT)
# ============================================================
def build_highspy_model(base_df, scenarios, K):
    T = 24
    omega_list = sorted(scenarios["scenario_id"].unique())
    scenario_probs = scenarios[["scenario_id", "probability"]].drop_duplicates().set_index("scenario_id")["probability"].to_dict()

    L_t = base_df["load_forecast"].values
    W_on_fc = base_df["wind_on_forecast"].values
    W_off_fc = base_df["wind_off_forecast"].values
    PV_fc = base_df["pv_forecast"].values
    lambda_DA = base_df["forecast_hybrid"].values
    lambda_RT = base_df["forecast_hybrid"].values

    err_data = {}
    for omega in omega_list:
        sub = scenarios[scenarios["scenario_id"] == omega]
        err_data[omega] = {
            "load": sub["load_error_bc"].values,
            "wind_on": sub["wind_on_error_bc"].values,
            "wind_off": sub["wind_off_error_bc"].values,
            "pv": sub["pv_error_bc"].values,
        }

    model = highspy.Highs()
    model.setOptionValue("output_flag", False)

    vars_dict = {}

    # --- First-stage variables ---
    for t in range(T):
        vars_dict[("x_DA", t)] = model.addVariable(lb=-P_MAX, ub=P_MAX, obj=0.0, name=f"x_DA_{t}")
        vars_dict[("p_ch", t)] = model.addVariable(lb=0.0, ub=P_CH_MAX, obj=0.0, name=f"p_ch_{t}")
        vars_dict[("p_dis", t)] = model.addVariable(lb=0.0, ub=P_DIS_MAX, obj=0.0, name=f"p_dis_{t}")
        vars_dict[("E", t)] = model.addVariable(lb=E_MIN, ub=E_MAX, obj=0.0, name=f"E_{t}")
        vars_dict[("z_ch", t)] = model.addVariable(lb=0.0, ub=1.0, obj=0.0, type=highspy.HighsVarType.kInteger, name=f"z_ch_{t}")
        vars_dict[("DR_plus", t)] = model.addVariable(lb=0.0, ub=DR_PLUS_MAX, obj=0.0, name=f"DR_plus_{t}")
        vars_dict[("DR_minus", t)] = model.addVariable(lb=0.0, ub=DR_MINUS_MAX, obj=0.0, name=f"DR_minus_{t}")

    # --- Scenario variables ---
    for omega in omega_list:
        for t in range(T):
            vars_dict[("p_PV", omega, t)] = model.addVariable(lb=0.0, ub=50.0, obj=0.0, name=f"p_PV_{omega}_{t}")
            vars_dict[("p_W", omega, t)] = model.addVariable(lb=0.0, ub=100.0, obj=0.0, name=f"p_W_{omega}_{t}")
            vars_dict[("p_DG", omega, t)] = model.addVariable(lb=P_DG_MIN, ub=P_DG_MAX, obj=0.0, name=f"p_DG_{omega}_{t}")
            vars_dict[("I_pos", omega, t)] = model.addVariable(lb=0.0, ub=M_BIG, obj=0.0, name=f"I_pos_{omega}_{t}")
            vars_dict[("I_neg", omega, t)] = model.addVariable(lb=0.0, ub=M_BIG, obj=0.0, name=f"I_neg_{omega}_{t}")
            vars_dict[("u_imb", omega, t)] = model.addVariable(lb=0.0, ub=1.0, obj=0.0, type=highspy.HighsVarType.kInteger, name=f"u_imb_{omega}_{t}")

    # --- CVaR variables ---
    eta_VaR = model.addVariable(lb=-1e6, ub=1e6, obj=0.0, name="eta_VaR")
    xi = {}
    for omega in omega_list:
        xi[omega] = model.addVariable(lb=0.0, ub=1e6, obj=0.0, name=f"xi_{omega}")

    # --- Objective ---
    obj_expr = []

    bess_cost_expr = DEG_COST * sum(vars_dict[("p_ch", t)] + vars_dict[("p_dis", t)] for t in range(T))
    dr_cost_expr = DR_COST * sum(vars_dict[("DR_plus", t)] + vars_dict[("DR_minus", t)] for t in range(T))

    for omega in omega_list:
        prob = scenario_probs[omega]
        rev_expr = sum(lambda_DA[t] * vars_dict[("x_DA", t)] + lambda_RT[t] * (vars_dict[("I_neg", omega, t)] - vars_dict[("I_pos", omega, t)]) for t in range(T))
        dg_cost_scen = sum(DG_COST * vars_dict[("p_DG", omega, t)] for t in range(T))
        imb_cost_scen = sum(C_IMB_PLUS * lambda_DA[t] * vars_dict[("I_pos", omega, t)] + C_IMB_MINUS * lambda_DA[t] * vars_dict[("I_neg", omega, t)] for t in range(T))
        scenario_specific = rev_expr - dg_cost_scen - imb_cost_scen
        obj_expr.append(prob * scenario_specific)

    obj_expr.append(-bess_cost_expr)
    obj_expr.append(-dr_cost_expr)

    cvar_expr = eta_VaR + (1/(1-ALPHA)) * sum(scenario_probs[omega] * xi[omega] for omega in omega_list)
    obj_expr.append(-LAMBDA_RISK * cvar_expr)

    model.maximize(sum(obj_expr))

    # --- Constraints ---

    # 1. BESS SOC dynamics
    for t in range(T):
        if t == 0:
            model.addConstr(vars_dict[("E", t)] == E_INIT + ETA_CH * vars_dict[("p_ch", t)] - (1/ETA_DIS) * vars_dict[("p_dis", t)])
        else:
            model.addConstr(vars_dict[("E", t)] == vars_dict[("E", t-1)] + ETA_CH * vars_dict[("p_ch", t)] - (1/ETA_DIS) * vars_dict[("p_dis", t)])

    # 2. BESS exclusivity
    for t in range(T):
        model.addConstr(vars_dict[("p_ch", t)] <= P_CH_MAX * vars_dict[("z_ch", t)])
        model.addConstr(vars_dict[("p_dis", t)] <= P_DIS_MAX * (1 - vars_dict[("z_ch", t)]))

    # 3. DR neutrality
    model.addConstr(sum(vars_dict[("DR_plus", t)] for t in range(T)) == sum(vars_dict[("DR_minus", t)] for t in range(T)))

    # 4. Power balance (corrected) and renewable bounds and imbalance exclusivity
    for omega in omega_list:
        for t in range(T):
            pv_err = err_data[omega]["pv"][t]
            w_on_err = err_data[omega]["wind_on"][t]
            w_off_err = err_data[omega]["wind_off"][t]
            load_err = err_data[omega]["load"][t]

            pv_act = max(0, PV_fc[t] + pv_err)
            w_act = max(0, (W_on_fc[t] + W_off_fc[t]) + (w_on_err + w_off_err))
            pv_act = min(pv_act, 50.0)
            w_act = min(w_act, 100.0)
            load_act = L_t[t] + load_err

            # Generation
            gen = (vars_dict[("p_PV", omega, t)] + vars_dict[("p_W", omega, t)] + vars_dict[("p_DG", omega, t)]
                   + vars_dict[("p_dis", t)] - vars_dict[("p_ch", t)])
            # Adjusted load
            load_adj = load_act - vars_dict[("DR_plus", t)] + vars_dict[("DR_minus", t)]

            # CORRECTED BALANCE: gen - load_adj == x_DA + I_neg - I_pos
            model.addConstr(gen - load_adj - vars_dict[("x_DA", t)] - vars_dict[("I_neg", omega, t)] + vars_dict[("I_pos", omega, t)] == 0)

            # Renewable bounds
            model.addConstr(vars_dict[("p_PV", omega, t)] <= pv_act)
            model.addConstr(vars_dict[("p_W", omega, t)] <= w_act)

            # Imbalance mutual exclusivity
            model.addConstr(vars_dict[("I_pos", omega, t)] <= M_BIG * vars_dict[("u_imb", omega, t)])
            model.addConstr(vars_dict[("I_neg", omega, t)] <= M_BIG * (1 - vars_dict[("u_imb", omega, t)]))

    # 5. CVaR constraints
    for omega in omega_list:
        rev_expr = sum(lambda_DA[t] * vars_dict[("x_DA", t)] + lambda_RT[t] * (vars_dict[("I_neg", omega, t)] - vars_dict[("I_pos", omega, t)]) for t in range(T))
        dg_cost_scen = sum(DG_COST * vars_dict[("p_DG", omega, t)] for t in range(T))
        imb_cost_scen = sum(C_IMB_PLUS * lambda_DA[t] * vars_dict[("I_pos", omega, t)] + C_IMB_MINUS * lambda_DA[t] * vars_dict[("I_neg", omega, t)] for t in range(T))
        bess_cost_expr_local = DEG_COST * sum(vars_dict[("p_ch", t)] + vars_dict[("p_dis", t)] for t in range(T))
        dr_cost_expr_local = DR_COST * sum(vars_dict[("DR_plus", t)] + vars_dict[("DR_minus", t)] for t in range(T))
        loss_expr = -(rev_expr - dg_cost_scen - imb_cost_scen - bess_cost_expr_local - dr_cost_expr_local)
        model.addConstr(xi[omega] >= loss_expr - eta_VaR)

    return model, vars_dict, eta_VaR, xi

# ============================================================
# MAIN
# ============================================================
def main():
    print("\n==============================================")
    print(" ALOCABID HIGHSPY (FIXED BALANCE CONSTRAINT)")
    print("==============================================")

    # --- Dummy base data ---
    T = 24
    base_df = pd.DataFrame({
        "timestamp": pd.date_range("2025-07-01", periods=T, freq="h", tz="Europe/Berlin"),
        "load_forecast": np.random.uniform(150, 250, T),
        "wind_on_forecast": np.random.uniform(0.3, 0.8, T),
        "wind_off_forecast": np.random.uniform(0.1, 0.3, T),
        "pv_forecast": np.random.uniform(0.0, 0.5, T),
        "forecast_hybrid": np.random.uniform(40, 80, T)
    })

    for K in [30, 50, 100]:
        print(f"\n--- Solving K={K} ---")
        scenarios = load_reduced_scenarios(K)
        model, vars_dict, eta_VaR, xi = build_highspy_model(base_df, scenarios, K)

        start_time = time.perf_counter()
        status = model.run()
        runtime = time.perf_counter() - start_time

        obj_val = model.getObjectiveValue()
        model_status = model.getModelStatus()
        print(f"Status: {status}, ModelStatus: {model_status}, Objective: {obj_val:.2f}, Runtime: {runtime:.2f}s")

        if obj_val != float('inf') and obj_val != float('-inf') and model_status == highspy.HighsModelStatus.kOptimal:
            result = {
                "K": K,
                "status": str(status),
                "model_status": str(model_status),
                "objective": obj_val,
                "runtime": runtime
            }
            with open(RESULTS_DIR / f"highspy_result_K{K}.json", "w") as f:
                json.dump(result, f, indent=2)
        else:
            print(f"Model not optimal. Status: {model_status}")

    print("\n[OK] Highspy execution complete.")

if __name__ == "__main__":
    main()

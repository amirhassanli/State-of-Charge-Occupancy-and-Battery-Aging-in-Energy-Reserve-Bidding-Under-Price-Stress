#!/usr/bin/env python3
"""Re-solve Gate-10 models and regenerate IEEE figures WITHOUT internal titles."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from ieee_style import apply_ieee, disable_internal_titles, COL, MODEL_ORDER, MODEL_SHORT
disable_internal_titles()
apply_ieee()

from gate10_core import (
    VPPParams, build_hourly, build_scenarios, expected_scenario,
    actual_as_scenario, build_and_solve, evaluate_first_stage, empirical_cvar,
)
from run_pipeline import (
    overlay_retail, summarize_sol, fig_forecast_vs_actual, fig_hourly_profit,
    fig_profit_comparison, fig_cvar_comparison, fig_runtime_scaling,
    fig_scenario_fan, fig_corr, fig_kde_errors, fig_boxplot, fig_violin,
    fig_ecdf, fig_radar, fig_soc, fig_dg, fig_reserve, fig_imbalance,
    fig_heatmap, fig_sensitivity_lambda, fig_sensitivity_alpha, fig_rolling,
    fig_pareto, fig_da_bids, OP_DAY, PAPER_FIG, PAPER_SENS, PAPER_STAT, BASE_FIG,
)

def main():
    params = VPPParams()
    df = build_hourly(params)
    scen = build_scenarios(df, OP_DAY, params, K=params.K)
    scen_ev = expected_scenario(scen, params)
    scen_act = actual_as_scenario(scen, params)
    sols = {
        "B0": build_and_solve(scen_ev, params, "B0", lam=0.0, alpha=params.alpha, use_reserve=False),
        "B2": build_and_solve(scen, params, "B2", lam=params.lam, alpha=params.alpha, use_reserve=False),
        "P1": build_and_solve(scen, params, "P1", lam=params.lam, alpha=params.alpha, use_reserve=True),
    }
    recs_is, recs_oos = {}, {}
    for m in MODEL_ORDER:
        recs_is[m] = overlay_retail(evaluate_first_stage(sols[m], scen, params, use_reserve=sols[m]["use_reserve"]), scen.load, params.alpha)
        recs_oos[m] = overlay_retail(evaluate_first_stage(sols[m], scen_act, params, use_reserve=sols[m]["use_reserve"]), scen_act.load, params.alpha)
    summaries = []
    for m in MODEL_ORDER:
        s = summarize_sol(sols[m], recs_is[m], recs_oos[m])
        s["reserve_revenue_eur"] = float((sols[m]["rup"] * scen.r_up + sols[m]["rdn"] * scen.r_dn).sum())
        summaries.append(s)
    profit_df = pd.concat([
        pd.DataFrame({"model": m, "profit_eur": recs_is[m]["profit_s"]}) for m in MODEL_ORDER
    ], ignore_index=True)
    sens_df = pd.read_csv(PAPER_SENS / "sensitivity_P1_full_factorial.csv")
    scale_df = pd.read_csv(PAPER_SENS / "runtime_scaling.csv")
    roll_df = pd.read_csv(PAPER_STAT / "rolling_oos.csv")

    pairs = [
        (fig_forecast_vs_actual, (scen, PAPER_FIG / "Fig01_Forecast_vs_Actual.png")),
        (fig_hourly_profit, (recs_is, PAPER_FIG / "Fig02_Hourly_Profit.png")),
        (fig_profit_comparison, (summaries, recs_is, PAPER_FIG / "Fig03_Profit_Comparison.png")),
        (fig_cvar_comparison, (summaries, PAPER_FIG / "Fig04_CVaR_Comparison.png")),
        (fig_runtime_scaling, (scale_df, PAPER_FIG / "Fig05_Runtime_Scaling.png")),
        (fig_scenario_fan, (scen, PAPER_FIG / "Fig06_Scenario_Fan.png")),
        (fig_corr, (scen, PAPER_FIG / "Fig07_Correlation_Matrix.png")),
        (fig_kde_errors, (scen, PAPER_FIG / "Fig08_Error_KDE.png")),
        (fig_boxplot, (profit_df, PAPER_FIG / "Fig09_Boxplot_Profit.png")),
        (fig_violin, (profit_df, PAPER_FIG / "Fig10_Violin_Profit.png")),
        (fig_ecdf, (profit_df, PAPER_FIG / "Fig11_ECDF_Profit.png")),
        (fig_radar, (summaries, recs_is, scale_df, PAPER_FIG / "Fig12_Radar.png")),
        (fig_soc, (recs_is, recs_oos, params, PAPER_FIG / "Fig13_Battery_SoC.png")),
        (fig_dg, (recs_is, recs_oos, PAPER_FIG / "Fig14_DG_Dispatch.png")),
        (fig_reserve, (sols, PAPER_FIG / "Fig15_Reserve_Schedule.png")),
        (fig_imbalance, (recs_is, recs_oos, PAPER_FIG / "Fig16_Imbalance.png")),
        (fig_heatmap, (sols, recs_is, PAPER_FIG / "Fig17_Heatmap_Decisions.png")),
        (fig_sensitivity_lambda, (sens_df, PAPER_FIG / "Fig18_Sensitivity_lambda.png")),
        (fig_sensitivity_alpha, (sens_df, PAPER_FIG / "Fig19_Sensitivity_alpha.png")),
        (fig_rolling, (roll_df, PAPER_FIG / "Fig20_Rolling_OOS.png")),
        (fig_pareto, (profit_df, summaries, PAPER_FIG / "Fig21_Pareto_Profit_Risk.png")),
        (fig_da_bids, (sols, scen, PAPER_FIG / "Fig22_DA_Energy_Bids.png")),
    ]
    for fn, args in pairs:
        fn(*args)
        print("wrote", args[-1].name)
    # also overwrite baseline figs without titles? NO — baseline is frozen.
    print("done untitled figures")

if __name__ == "__main__":
    main()

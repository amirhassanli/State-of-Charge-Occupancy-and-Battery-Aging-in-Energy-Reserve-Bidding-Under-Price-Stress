#!/usr/bin/env python3
"""Gate 10 baseline freeze + Phase A–D paper results (figures, sensitivity, stats, IEEE tables)."""

from __future__ import annotations

import json
import shutil
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
import seaborn as sns
from scipy import stats
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, NamedStyle
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.chart import BarChart, Reference, LineChart

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate10_core import (
    VPPParams,
    build_hourly,
    complete_days,
    slice_day,
    build_scenarios,
    expected_scenario,
    actual_as_scenario,
    build_and_solve,
    evaluate_first_stage,
    empirical_cvar,
    numpy_to_list,
    PROC,
    ROOT,
)
from ieee_style import apply_ieee, savefig, COL, MODEL_ORDER, MODEL_SHORT, hours

warnings.filterwarnings("ignore", category=UserWarning)

BASE = ROOT / "Gate10_REAL_RESULTS"
BASE_FIG = BASE / "figures"
PAPER = ROOT / "Gate10_PAPER_EXTENSION"
PAPER_FIG = PAPER / "figures"
PAPER_TAB = PAPER / "tables"
PAPER_SENS = PAPER / "sensitivity"
PAPER_STAT = PAPER / "stats"
BASELINE_COPY = ROOT / "Gate10_REAL_RESULTS_BASELINE_2026-08-21"

OP_DAY = "2026-08-19"  # last complete typical weekday with full SMARD actuals+forecasts
RETAIL_EUR_MWH = 180.0  # industrial energy-only contract (reporting; load is exogenous)


def ensure_dirs():
    for p in [BASE, BASE_FIG, PAPER, PAPER_FIG, PAPER_TAB, PAPER_SENS, PAPER_STAT, PROC]:
        p.mkdir(parents=True, exist_ok=True)


def overlay_retail(rec, load_arr, alpha, rate=RETAIL_EUR_MWH):
    """Add exogenous load-service revenue so reported profit is an aggregator P&L."""
    rec = dict(rec)
    load_arr = np.asarray(load_arr, dtype=float)
    rec["profit_st"] = rec["profit_st"] + rate * load_arr
    rec["profit_s"] = rec["profit_st"].sum(axis=1)
    rec["e_profit"] = float(rec["profit_s"] @ rec["pi"])
    rec["cvar_emp"] = empirical_cvar(rec["profit_s"], alpha)
    rec["retail_rate"] = rate
    rec["retail_revenue_eur"] = float((rate * load_arr).mean(axis=0).sum()) if load_arr.ndim == 2 else float(rate * load_arr.sum())
    return rec


def first_stage_pack(sol):
    return {"pda": sol["pda"].copy(), "rup": sol["rup"].copy(), "rdn": sol["rdn"].copy()}


def scenario_profit_table(sol, scen, rec):
    K = rec["K"]
    df = pd.DataFrame(
        {
            "scenario": np.arange(K),
            "profit_eur": rec["profit_s"],
            "imb_short_mwh": rec["ishort"].sum(axis=1),
            "imb_long_mwh": rec["ilong"].sum(axis=1),
            "dg_mwh": rec["pdg"].sum(axis=1),
            "charge_mwh": rec["pch"].sum(axis=1),
            "discharge_mwh": rec["pdis"].sum(axis=1),
        }
    )
    df["model"] = sol["model"]
    return df


def summarize_sol(sol, rec_is, rec_oos, runtime_note=""):
    return {
        "model": sol["model"],
        "status": sol["status"],
        "success": sol["success"],
        "day": sol["day"],
        "K": sol["K"],
        "lam": sol["lam"],
        "alpha": sol["alpha"],
        "use_reserve": sol["use_reserve"],
        "n_vars": sol["n_vars"],
        "n_eq": sol["n_eq"],
        "n_ineq": sol["n_ineq"],
        "runtime_s": sol["runtime_s"],
        "highs_nit": sol["highs_nit"],
        "in_sample_E_profit_eur": rec_is["e_profit"],
        "in_sample_CVaR_eur": rec_is["cvar_emp"],
        "in_sample_std_eur": float(np.std(rec_is["profit_s"], ddof=1)) if rec_is["K"] > 1 else 0.0,
        "in_sample_p5_eur": float(np.quantile(rec_is["profit_s"], 0.05)),
        "in_sample_p50_eur": float(np.quantile(rec_is["profit_s"], 0.50)),
        "in_sample_p95_eur": float(np.quantile(rec_is["profit_s"], 0.95)),
        "realized_profit_eur": rec_oos["e_profit"],
        "realized_cvar_proxy_eur": rec_oos["cvar_emp"],
        "DA_energy_mwh": float(sol["pda"].sum()),
        "reserve_up_mw_h": float(sol["rup"].sum()),
        "reserve_dn_mw_h": float(sol["rdn"].sum()),
        "obj": sol["obj"],
        "note": runtime_note,
    }


# ===========================================================================
# FIGURES
# ===========================================================================

def fig_forecast_vs_actual(scen, path):
    apply_ieee()
    t = hours()
    fig, ax = plt.subplots(2, 2, figsize=(7.16, 4.6), sharex=True)
    series = [
        (ax[0, 0], scen.price_fc, scen.price_act, "Day-ahead price (EUR/MWh)", None),
        (ax[0, 1], scen.load_fc, scen.load_act, "VPP load (MW)", None),
        (ax[1, 0], scen.pv_fc, scen.pv_act, "On-site PV (MW)", None),
        (ax[1, 1], scen.wind_fc, scen.wind_act, "On-site wind (MW)", None),
    ]
    for a, fc, act, ylab, _ in series:
        a.plot(t, fc, color=COL["forecast"], lw=1.4, label="Day-ahead forecast")
        a.plot(t, act, color=COL["actual"], lw=1.2, ls="--", label="Realized")
        a.set_ylabel(ylab)
        a.grid(True, axis="y")
        a.set_xlim(0, 23)
    ax[0, 0].legend(loc="upper left")
    ax[1, 0].set_xlabel("Hour")
    ax[1, 1].set_xlabel("Hour")
    ax[1, 0].set_xticks(range(0, 24, 3))
    fig.suptitle(f"Forecast vs. realized — {scen.day} (SMARD DE-LU)", y=1.01, fontsize=10)
    fig.tight_layout()
    savefig(fig, path)


def fig_scenario_fan(scen, path):
    apply_ieee()
    t = hours()
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.8), sharex=True)
    panels = [
        (axes[0, 0], scen.price, scen.price_fc, scen.price_act, "Price (EUR/MWh)"),
        (axes[0, 1], scen.load, scen.load_fc, scen.load_act, "Load (MW)"),
        (axes[1, 0], scen.pv, scen.pv_fc, scen.pv_act, "PV (MW)"),
        (axes[1, 1], scen.wind, scen.wind_fc, scen.wind_act, "Wind (MW)"),
    ]
    for a, X, fc, act, ylab in panels:
        for k in range(min(X.shape[0], 80)):
            a.plot(t, X[k], color=COL["B0"], alpha=0.12, lw=0.6)
        q10, q50, q90 = np.quantile(X, [0.1, 0.5, 0.9], axis=0)
        a.fill_between(t, q10, q90, color=COL["B0"], alpha=0.18, label="P10–P90")
        a.plot(t, q50, color=COL["B0"], lw=1.3, label="Scenario median")
        a.plot(t, fc, color=COL["forecast"], lw=1.3, label="Forecast")
        a.plot(t, act, color=COL["actual"], lw=1.2, ls="--", label="Actual")
        a.set_ylabel(ylab)
        a.grid(True, axis="y")
        a.set_xlim(0, 23)
    axes[0, 0].legend(loc="best", ncol=2, fontsize=6.5)
    axes[1, 0].set_xlabel("Hour")
    axes[1, 1].set_xlabel("Hour")
    fig.suptitle(f"Scenario fan (K={scen.K}) — block-bootstrap forecast errors", y=1.01, fontsize=10)
    fig.tight_layout()
    savefig(fig, path)


def fig_profit_comparison(summaries, recs_is, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(3.6, 3.3))
    models = [s["model"] for s in summaries]
    e = [s["in_sample_E_profit_eur"] for s in summaries]
    r = [s["realized_profit_eur"] for s in summaries]
    x = np.arange(len(models))
    w = 0.36
    ax.bar(x - w / 2, e, w, color=[COL[m] for m in models], alpha=0.85, label="In-sample E[profit]")
    ax.bar(x + w / 2, r, w, color=[COL[m] for m in models], alpha=0.40, edgecolor=[COL[m] for m in models], hatch="//", label="Realized (OOS)")
    # error bars from scenario std
    stds = [s["in_sample_std_eur"] for s in summaries]
    ax.errorbar(x - w / 2, e, yerr=stds, fmt="none", ecolor="k", capsize=2.5, lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([MODEL_SHORT[m] for m in models])
    ax.set_ylabel("Profit (EUR / day)")
    ax.grid(True, axis="y")
    ax.legend(loc="best")
    ax.set_title("Daily profit by model")
    fig.tight_layout()
    savefig(fig, path)


def fig_cvar_comparison(summaries, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(3.6, 3.3))
    models = [s["model"] for s in summaries]
    c = [s["in_sample_CVaR_eur"] for s in summaries]
    e = [s["in_sample_E_profit_eur"] for s in summaries]
    x = np.arange(len(models))
    w = 0.36
    ax.bar(x - w / 2, e, w, color=[COL[m] for m in models], alpha=0.35, label="E[profit]")
    ax.bar(x + w / 2, c, w, color=[COL[m] for m in models], alpha=0.9, label=r"CVaR$_{0.95}$")
    ax.set_xticks(x)
    ax.set_xticklabels([MODEL_SHORT[m] for m in models])
    ax.set_ylabel("EUR / day")
    ax.grid(True, axis="y")
    ax.legend()
    ax.set_title("Expected profit vs. CVaR")
    fig.tight_layout()
    savefig(fig, path)


def fig_hourly_profit(recs_is, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(7.16, 3.1))
    t = hours()
    for m, rec in recs_is.items():
        mu = rec["profit_st"].mean(axis=0)
        lo, hi = np.quantile(rec["profit_st"], [0.1, 0.9], axis=0)
        ax.fill_between(t, lo, hi, color=COL[m], alpha=0.15)
        ax.plot(t, mu, color=COL[m], lw=1.5, label=MODEL_SHORT[m])
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xlabel("Hour")
    ax.set_ylabel("Hourly profit (EUR)")
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 2))
    ax.grid(True, axis="y")
    ax.legend(ncol=3)
    ax.set_title("Hourly profit (in-sample mean and P10–P90)")
    fig.tight_layout()
    savefig(fig, path)


def fig_soc(recs_is, recs_oos, params, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(7.16, 3.2))
    t = hours()
    soc_min = params.soc_min_frac * params.e_batt_mwh
    soc_max = params.soc_max_frac * params.e_batt_mwh
    ax.axhspan(0, soc_min, color="#f4cccc", alpha=0.35, zorder=0)
    ax.axhspan(soc_max, params.e_batt_mwh, color="#f4cccc", alpha=0.35, zorder=0)
    ax.axhline(soc_min, color="#cc0000", lw=0.6, ls=":")
    ax.axhline(soc_max, color="#cc0000", lw=0.6, ls=":")
    for m, rec in recs_is.items():
        mu = rec["soc"].mean(axis=0)
        lo, hi = np.quantile(rec["soc"], [0.1, 0.9], axis=0)
        ax.fill_between(t, lo, hi, color=COL[m], alpha=0.12)
        ax.plot(t, mu, color=COL[m], lw=1.5, label=f"{MODEL_SHORT[m]} (IS mean)")
        ax.plot(t, recs_oos[m]["soc"][0], color=COL[m], lw=1.1, ls="--")
    ax.plot([], [], color="k", ls="--", lw=1.0, label="Realized SoC")
    ax.set_xlabel("Hour")
    ax.set_ylabel("Battery SoC (MWh)")
    ax.set_xlim(0, 23)
    ax.set_ylim(0, params.e_batt_mwh)
    ax.set_xticks(range(0, 24, 2))
    ax.grid(True, axis="y")
    ax.legend(ncol=2, loc="upper right")
    ax.set_title("Battery state of charge")
    fig.tight_layout()
    savefig(fig, path)


def fig_dg(recs_is, recs_oos, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(7.16, 3.1))
    t = hours()
    for m, rec in recs_is.items():
        ax.plot(t, rec["pdg"].mean(axis=0), color=COL[m], lw=1.5, label=f"{MODEL_SHORT[m]} IS")
        ax.plot(t, recs_oos[m]["pdg"][0], color=COL[m], lw=1.05, ls="--")
    ax.set_xlabel("Hour")
    ax.set_ylabel("DG power (MW)")
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 2))
    ax.grid(True, axis="y")
    ax.legend(ncol=3)
    ax.set_title("Distributed-generation dispatch")
    fig.tight_layout()
    savefig(fig, path)


def fig_reserve(sols, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(7.16, 3.1))
    t = hours()
    for m, sol in sols.items():
        ax.step(t, sol["rup"], where="mid", color=COL[m], lw=1.4, label=f"{MODEL_SHORT[m]}  $r^{{\\uparrow}}$")
        ax.step(t, -sol["rdn"], where="mid", color=COL[m], lw=1.2, ls="--", label=f"{MODEL_SHORT[m]}  $r^{{\\downarrow}}$")
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xlabel("Hour")
    ax.set_ylabel("Reserve allocation (MW)")
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 2))
    ax.grid(True, axis="y")
    ax.legend(ncol=3, fontsize=7)
    ax.set_title("Day-ahead reserve schedule (up positive, down negative)")
    fig.tight_layout()
    savefig(fig, path)


def fig_imbalance(recs_is, recs_oos, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(7.16, 3.2))
    t = hours()
    for m, rec in recs_is.items():
        net = rec["ilong"].mean(axis=0) - rec["ishort"].mean(axis=0)
        ax.plot(t, net, color=COL[m], lw=1.5, label=MODEL_SHORT[m])
        ax.plot(t, recs_oos[m]["ilong"][0] - recs_oos[m]["ishort"][0], color=COL[m], ls="--", lw=1.0)
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xlabel("Hour")
    ax.set_ylabel("Net imbalance (MW)  long $+$, short $-$")
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 2))
    ax.grid(True, axis="y")
    ax.legend(ncol=3)
    ax.set_title("Energy imbalance (in-sample mean; dashed = realized)")
    fig.tight_layout()
    savefig(fig, path)


def fig_boxplot(profit_df, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    data = [profit_df.loc[profit_df.model == m, "profit_eur"].values for m in MODEL_ORDER]
    bp = ax.boxplot(
        data,
        tick_labels=[MODEL_SHORT[m] for m in MODEL_ORDER],
        patch_artist=True,
        widths=0.55,
        showfliers=True,
        medianprops=dict(color="k", lw=1.2),
        flierprops=dict(marker="o", ms=3, alpha=0.5),
        whiskerprops=dict(lw=0.8),
        capprops=dict(lw=0.8),
    )
    for patch, m in zip(bp["boxes"], MODEL_ORDER):
        patch.set_facecolor(COL[m])
        patch.set_alpha(0.75)
    ax.set_ylabel("Scenario profit (EUR)")
    ax.grid(True, axis="y")
    ax.set_title("Scenario profit distribution")
    fig.tight_layout()
    savefig(fig, path)


def fig_violin(profit_df, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    sns.violinplot(
        data=profit_df,
        x="model",
        y="profit_eur",
        hue="model",
        order=MODEL_ORDER,
        palette=COL,
        inner="quartile",
        cut=0,
        ax=ax,
        linewidth=0.8,
        legend=False,
    )
    ax.set_xticks(range(len(MODEL_ORDER)))
    ax.set_xticklabels([MODEL_SHORT[m] for m in MODEL_ORDER])
    ax.set_xlabel("")
    ax.set_ylabel("Scenario profit (EUR)")
    ax.set_title("Violin plot of scenario profits")
    ax.grid(True, axis="y")
    fig.tight_layout()
    savefig(fig, path)


def fig_ecdf(profit_df, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    for m in MODEL_ORDER:
        x = np.sort(profit_df.loc[profit_df.model == m, "profit_eur"].values)
        y = np.arange(1, len(x) + 1) / len(x)
        ax.step(x, y, where="post", color=COL[m], lw=1.5, label=MODEL_SHORT[m])
    ax.set_xlabel("Scenario profit (EUR)")
    ax.set_ylabel("Empirical CDF")
    ax.set_ylim(0, 1)
    ax.grid(True)
    ax.legend()
    ax.set_title("ECDF of scenario profit")
    fig.tight_layout()
    savefig(fig, path)


def fig_heatmap(sols, recs_is, path):
    apply_ieee()
    # P1 decisions primarily
    sol = sols["P1"]
    rec = recs_is["P1"]
    rows = {
        "DA bid (MW)": sol["pda"],
        "Reserve up (MW)": sol["rup"],
        "Reserve down (MW)": sol["rdn"],
        "DG mean (MW)": rec["pdg"].mean(0),
        "Charge mean (MW)": rec["pch"].mean(0),
        "Discharge mean (MW)": rec["pdis"].mean(0),
        "SoC mean (MWh)": rec["soc"].mean(0),
        "Imb. net mean (MW)": rec["ilong"].mean(0) - rec["ishort"].mean(0),
        "Hourly profit (EUR)": rec["profit_st"].mean(0),
    }
    M = np.vstack([v for v in rows.values()])
    # row-wise z-score for visibility, keep original in colorbar? Better: plot raw with diverging for signed rows.
    fig, ax = plt.subplots(figsize=(7.16, 3.8))
    # normalize each row to [-1,1] for display
    Mn = np.zeros_like(M)
    for i in range(M.shape[0]):
        a = np.max(np.abs(M[i]))
        Mn[i] = M[i] / a if a > 1e-9 else M[i]
    im = ax.imshow(Mn, aspect="auto", cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(list(rows.keys()), fontsize=7.5)
    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h:02d}" for h in range(24)], fontsize=6.5)
    ax.set_xlabel("Hour")
    ax.set_title("P1 24-hour decision heatmap (row-normalised)")
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("row-normalised value")
    fig.tight_layout()
    savefig(fig, path)


def fig_corr(scen, path):
    apply_ieee()
    # hour-aggregated daily errors
    hist = scen.hist_errors
    mats = []
    labels = []
    # use hour-6,12,18 price/load/pv/wind errors
    hours_sel = [6, 12, 18]
    names = []
    cols = []
    for key, lab in [("e_price", "π"), ("e_load", "L"), ("e_pv", "PV"), ("e_wind", "W")]:
        E = np.vstack(hist[key].to_list())
        for h in hours_sel:
            cols.append(E[:, h])
            names.append(f"{lab}@{h:02d}")
    C = np.corrcoef(np.vstack(cols))
    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    im = ax.imshow(C, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(names)))
    ax.set_yticks(range(len(names)))
    ax.set_xticklabels(names, rotation=60, ha="right", fontsize=7)
    ax.set_yticklabels(names, fontsize=7)
    for i in range(len(names)):
        for j in range(len(names)):
            ax.text(j, i, f"{C[i, j]:.2f}", ha="center", va="center", fontsize=5.5, color="k" if abs(C[i, j]) < 0.7 else "w")
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    ax.set_title("Forecast-error correlation (selected hours)")
    fig.tight_layout()
    savefig(fig, path)


def fig_kde_errors(scen, path):
    apply_ieee()
    hist = scen.hist_errors
    fig, ax = plt.subplots(2, 2, figsize=(7.16, 4.6))
    specs = [
        (ax[0, 0], "e_price", "Price error (EUR/MWh)", COL["navy"]),
        (ax[0, 1], "e_load", "Load error (MW)", COL["vermilion"]),
        (ax[1, 0], "e_pv", "PV error (MW)", COL["forecast"]),
        (ax[1, 1], "e_wind", "Wind error (MW)", COL["green"]),
    ]
    for a, key, xlab, c in specs:
        E = np.vstack(hist[key].to_list()).ravel()
        sns.kdeplot(E, ax=a, fill=True, color=c, lw=1.2, bw_adjust=0.9)
        a.axvline(0, color="k", lw=0.6, ls="--")
        a.axvline(np.mean(E), color=c, lw=1.0)
        a.set_xlabel(xlab)
        a.set_ylabel("Density")
        a.grid(True, axis="y")
        a.text(0.02, 0.92, f"MAE={np.mean(np.abs(E)):.2f}", transform=a.transAxes, fontsize=7)
    fig.suptitle("Kernel densities of day-ahead forecast errors", y=1.01, fontsize=10)
    fig.tight_layout()
    savefig(fig, path)


def fig_radar(summaries, recs_is, runtimes_k, path):
    apply_ieee()
    # metrics: E[profit], CVaR, -std, -|imbalance|, reserve revenue, -runtime
    labels = ["E[profit]", r"CVaR$_{0.95}$", "Low risk\n(1/σ)", "Energy\nbalance", "Reserve\nrevenue", "Speed"]
    raw = {m: [] for m in MODEL_ORDER}
    e = {s["model"]: s["in_sample_E_profit_eur"] for s in summaries}
    c = {s["model"]: s["in_sample_CVaR_eur"] for s in summaries}
    sig = {s["model"]: max(s["in_sample_std_eur"], 1e-6) for s in summaries}
    imb = {m: float((recs_is[m]["ishort"] + recs_is[m]["ilong"]).mean()) for m in MODEL_ORDER}
    rev = {s["model"]: float((np.asarray(s.get("_rup_rev", 0)))) for s in summaries}
    # compute reserve revenue from sols stored in summaries? pass via extra
    for s in summaries:
        pass
    # We'll fill reserve revenue / runtime from summaries extra keys if present
    rrev = {s["model"]: s.get("reserve_revenue_eur", 0.0) for s in summaries}
    rt = {s["model"]: max(s["runtime_s"], 1e-6) for s in summaries}

    metrics = {
        "E[profit]": e,
        "cvar": c,
        "invstd": {m: 1.0 / sig[m] for m in MODEL_ORDER},
        "bal": {m: 1.0 / (1.0 + imb[m]) for m in MODEL_ORDER},
        "rev": rrev,
        "spd": {m: 1.0 / rt[m] for m in MODEL_ORDER},
    }
    # min-max across models to [0.15, 1]
    keys = list(metrics.keys())
    vals = {m: [] for m in MODEL_ORDER}
    for k in keys:
        xs = np.array([metrics[k][m] for m in MODEL_ORDER], dtype=float)
        lo, hi = xs.min(), xs.max()
        if hi - lo < 1e-12:
            nrm = np.ones_like(xs)
        else:
            nrm = 0.18 + 0.82 * (xs - lo) / (hi - lo)
        for i, m in enumerate(MODEL_ORDER):
            vals[m].append(float(nrm[i]))

    N = len(labels)
    ang = np.linspace(0, 2 * np.pi, N, endpoint=False)
    ang = np.concatenate([ang, ang[:1]])
    fig, ax = plt.subplots(figsize=(4.2, 4.2), subplot_kw=dict(polar=True))
    for m in MODEL_ORDER:
        v = vals[m] + vals[m][:1]
        ax.plot(ang, v, color=COL[m], lw=1.6, label=MODEL_SHORT[m])
        ax.fill(ang, v, color=COL[m], alpha=0.12)
    ax.set_xticks(ang[:-1])
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["", "", "", ""], fontsize=6)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper right", bbox_to_anchor=(1.28, 1.12))
    ax.set_title("Multi-criteria profile (normalised)", pad=14)
    fig.tight_layout()
    savefig(fig, path)


def fig_pareto(profit_df, summaries, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(3.7, 3.4))
    for s in summaries:
        m = s["model"]
        ax.scatter(
            s["in_sample_std_eur"],
            s["in_sample_E_profit_eur"],
            s=90,
            color=COL[m],
            zorder=5,
            label=MODEL_SHORT[m],
            edgecolors="k",
            lw=0.4,
        )
        ax.scatter(
            s["in_sample_std_eur"],
            s["in_sample_CVaR_eur"],
            s=50,
            color=COL[m],
            marker="D",
            zorder=4,
            alpha=0.8,
        )
    ax.set_xlabel("Profit std. dev. (EUR)")
    ax.set_ylabel("EUR / day")
    ax.grid(True)
    h1 = Line2D([0], [0], marker="o", color="w", markerfacecolor="#555", markersize=8, label="E[profit]")
    h2 = Line2D([0], [0], marker="D", color="w", markerfacecolor="#555", markersize=7, label=r"CVaR$_{0.95}$")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles + [h1, h2], labels + ["E[profit]", r"CVaR$_{0.95}$"], loc="best", fontsize=7)
    ax.set_title("Profit–risk Pareto view")
    fig.tight_layout()
    savefig(fig, path)


def fig_runtime_scaling(scale_df, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(3.6, 3.3))
    for m in [c for c in scale_df.columns if c != "K"]:
        ax.plot(scale_df["K"], scale_df[m], marker="o", color=COL.get(m, "k"), lw=1.4, label=MODEL_SHORT.get(m, m))
    ax.set_xlabel("Number of scenarios $K$")
    ax.set_ylabel("HiGHS runtime (s)")
    ax.grid(True)
    ax.legend()
    ax.set_title("Runtime scaling vs. scenario count")
    fig.tight_layout()
    savefig(fig, path)


def fig_sensitivity_lambda(sens_df, path):
    apply_ieee()
    sub = sens_df[(sens_df.alpha == 0.95) & (sens_df.K == 50)].copy()
    fig, ax = plt.subplots(figsize=(3.7, 3.3))
    ax.plot(sub["lam"], sub["e_profit"], marker="o", color=COL["P1"], lw=1.5, label="E[profit]")
    ax.plot(sub["lam"], sub["cvar"], marker="s", color=COL["accent"], lw=1.5, label=r"CVaR$_{0.95}$")
    ax.plot(sub["lam"], sub["realized"], marker="^", color=COL["navy"], lw=1.2, ls="--", label="Realized")
    ax.set_xlabel(r"Risk aversion $\lambda$")
    ax.set_ylabel("EUR / day")
    ax.grid(True)
    ax.legend()
    ax.set_title(r"P1 sensitivity to $\lambda$ ($\alpha$=0.95, $K$=50)")
    fig.tight_layout()
    savefig(fig, path)


def fig_sensitivity_alpha(sens_df, path):
    apply_ieee()
    sub = sens_df[(sens_df.lam == 0.05) & (sens_df.K == 50)].copy()
    fig, ax = plt.subplots(figsize=(3.7, 3.3))
    ax.plot(sub["alpha"], sub["e_profit"], marker="o", color=COL["P1"], lw=1.5, label="E[profit]")
    ax.plot(sub["alpha"], sub["cvar"], marker="s", color=COL["accent"], lw=1.5, label="CVaR")
    ax.plot(sub["alpha"], sub["realized"], marker="^", color=COL["navy"], lw=1.2, ls="--", label="Realized")
    ax.set_xlabel(r"CVaR confidence $\alpha$")
    ax.set_ylabel("EUR / day")
    ax.grid(True)
    ax.legend()
    ax.set_title(r"P1 sensitivity to $\alpha$ ($\lambda$=0.05, $K$=50)")
    fig.tight_layout()
    savefig(fig, path)


def fig_rolling(roll_df, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(7.16, 3.2))
    days = roll_df["day"].unique()
    x = np.arange(len(days))
    for m in MODEL_ORDER:
        sub = roll_df[roll_df.model == m]
        ax.plot(x, sub["realized_profit_eur"].values, marker="o", ms=3.5, color=COL[m], lw=1.3, label=MODEL_SHORT[m])
    ax.set_xticks(x)
    ax.set_xticklabels([str(d)[5:] for d in days], rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Realized daily profit (EUR)")
    ax.set_xlabel("Operating day (2026)")
    ax.grid(True, axis="y")
    ax.legend(ncol=3)
    ax.set_title("Rolling out-of-sample settlement")
    fig.tight_layout()
    savefig(fig, path)


def fig_da_bids(sols, scen, path):
    apply_ieee()
    fig, ax = plt.subplots(figsize=(7.16, 3.1))
    t = hours()
    ax.plot(t, scen.price_act, color=COL["actual"], lw=1.0, ls=":", label="DA price (right)", alpha=0.0)  # placeholder
    ax2 = ax.twinx()
    ax2.spines["right"].set_visible(True)
    ax2.plot(t, scen.price_act, color="#888888", lw=1.0, ls=":", label="Actual DA price")
    ax2.set_ylabel("DA price (EUR/MWh)", color="#555")
    for m, sol in sols.items():
        ax.step(t, sol["pda"], where="mid", color=COL[m], lw=1.5, label=MODEL_SHORT[m])
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xlabel("Hour")
    ax.set_ylabel("DA energy bid (MW)  sell $+$")
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 2))
    ax.grid(True, axis="y")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, ncol=4, loc="upper left")
    ax.set_title("Day-ahead energy position")
    fig.tight_layout()
    savefig(fig, path)


# ===========================================================================
# STATISTICS
# ===========================================================================

def paired_stats(a, b, name_a, name_b, n_boot=8000, seed=20260821):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    d = a - b
    n = len(d)
    # t-test
    tstat, p_t = stats.ttest_rel(a, b)
    # wilcoxon
    try:
        wstat, p_w = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided", method="auto")
    except Exception:
        wstat, p_w = np.nan, np.nan
    # Cohen's d (paired)
    sd = np.std(d, ddof=1)
    d_cohen = float(d.mean() / sd) if sd > 1e-12 else 0.0
    # bootstrap CI of mean difference
    rng = np.random.default_rng(seed)
    boots = rng.choice(d, size=(n_boot, n), replace=True).mean(axis=1)
    ci = np.quantile(boots, [0.025, 0.975])
    return {
        "comparison": f"{name_a} − {name_b}",
        "n": int(n),
        "mean_A": float(a.mean()),
        "mean_B": float(b.mean()),
        "mean_diff": float(d.mean()),
        "std_diff": float(sd),
        "t_stat": float(tstat),
        "p_ttest": float(p_t),
        "wilcoxon_stat": float(wstat) if wstat == wstat else np.nan,
        "p_wilcoxon": float(p_w) if p_w == p_w else np.nan,
        "cohens_d_paired": float(d_cohen),
        "bootstrap_ci95_low": float(ci[0]),
        "bootstrap_ci95_high": float(ci[1]),
        "significant_0.05_ttest": bool(p_t < 0.05),
        "significant_0.05_wilcoxon": bool(p_w < 0.05) if p_w == p_w else False,
    }


# ===========================================================================
# EXCEL / TABLES
# ===========================================================================

THIN = Border(
    left=Side(style="thin", color="808080"),
    right=Side(style="thin", color="808080"),
    top=Side(style="thin", color="808080"),
    bottom=Side(style="thin", color="808080"),
)
HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
CELL_FONT = Font(name="Calibri", size=10)
TITLE_FONT = Font(name="Calibri", bold=True, size=13, color="1F4E79")
ALT_FILL = PatternFill("solid", fgColor="D6E3F0")
NOTE_FONT = Font(name="Calibri", italic=True, size=8, color="666666")


def style_sheet(ws, title, n_cols, note=None):
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = None
    if note:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n_cols)
        ws["A2"] = note
        ws["A2"].font = NOTE_FONT


def write_df(ws, df, start_row=3):
    # header
    for j, col in enumerate(df.columns, 1):
        cell = ws.cell(start_row, j, col)
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
        cell.border = THIN
    for i, row in enumerate(df.itertuples(index=False), start_row + 1):
        for j, val in enumerate(row, 1):
            cell = ws.cell(i, j, val)
            cell.font = CELL_FONT
            cell.border = THIN
            cell.alignment = Alignment(horizontal="center" if j > 1 else "left", vertical="center")
            if isinstance(val, float):
                if abs(val) >= 100 or abs(val) == 0:
                    cell.number_format = "0.00"
                elif abs(val) >= 1:
                    cell.number_format = "0.000"
                else:
                    cell.number_format = "0.0000"
            if (i - start_row) % 2 == 0:
                if cell.fill.fgColor is None or cell.fill.fgColor.rgb == "00000000":
                    cell.fill = ALT_FILL
    for j, col in enumerate(df.columns, 1):
        width = max(12, min(28, len(str(col)) + 4))
        ws.column_dimensions[get_column_letter(j)].width = width
    ws.row_dimensions[start_row].height = 28
    ws.auto_filter.ref = f"A{start_row}:{get_column_letter(df.shape[1])}{start_row + len(df)}"


def write_ieee_workbook(path, tables: dict, extra_sheets: dict):
    wb = Workbook()
    # cover
    ws = wb.active
    ws.title = "Cover"
    ws["A1"] = "Gate 10 — Risk-Averse Stochastic VPP Scheduling on SMARD Data"
    ws["A1"].font = Font(name="Calibri", bold=True, size=16, color="1F4E79")
    ws.merge_cells("A1:F1")
    lines = [
        ("Operating day", OP_DAY),
        ("Bidding zone", "DE-LU (Germany / Luxembourg)"),
        ("Data source", "Bundesnetzagentur | SMARD.de via Energy-Charts API (CC BY 4.0)"),
        ("Solver", "HiGHS (scipy.optimize.linprog, method='highs')"),
        ("Models", "B0 expected-value; B2 two-stage mean–CVaR energy-only; P1 proposed joint energy–reserve mean–CVaR"),
        ("Baseline freeze", "Gate10_REAL_RESULTS_BASELINE_2026-08-21"),
        ("Generated", pd.Timestamp.now(tz="Europe/Berlin").strftime("%Y-%m-%d %H:%M %Z")),
    ]
    ws["A3"] = "Item"
    ws["B3"] = "Value"
    ws["A3"].fill = HDR_FILL
    ws["B3"].fill = HDR_FILL
    ws["A3"].font = HDR_FONT
    ws["B3"].font = HDR_FONT
    for i, (k, v) in enumerate(lines, 4):
        ws.cell(i, 1, k).font = Font(name="Calibri", bold=True, size=11)
        ws.cell(i, 2, v).font = CELL_FONT
        ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=6)
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 28

    for name, (title, note, df) in tables.items():
        w = wb.create_sheet(name[:31])
        style_sheet(w, title, n_cols=df.shape[1], note=note)
        write_df(w, df, start_row=3)

    for name, df in extra_sheets.items():
        w = wb.create_sheet(name[:31])
        style_sheet(w, name, n_cols=df.shape[1], note="Supporting data.")
        write_df(w, df, start_row=3)

    wb.save(path)


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    ensure_dirs()
    t_all = time.perf_counter()
    params = VPPParams()
    print("== Building hourly SMARD/VPP panel ==")
    df = build_hourly(params)
    days = complete_days(df)
    print(f"  hours={len(df)} complete_days={len(days)} range={df.index.min()} → {df.index.max()}")

    print(f"== Scenarios for operating day {OP_DAY}  K={params.K} ==")
    scen = build_scenarios(df, OP_DAY, params, K=params.K)
    print("  diagnostics", json.dumps(scen.diagnostics, indent=2))
    scen_ev = expected_scenario(scen, params)
    scen_act = actual_as_scenario(scen, params)

    print("== Solving B0 / B2 / P1 ==")
    sols = {}
    t0 = time.perf_counter()
    sols["B0"] = build_and_solve(scen_ev, params, "B0", lam=0.0, alpha=params.alpha, use_reserve=False)
    print(f"  B0 {sols['B0']['status']}  obj={sols['B0']['obj']:.2f}  t={sols['B0']['runtime_s']:.3f}s")
    sols["B2"] = build_and_solve(scen, params, "B2", lam=params.lam, alpha=params.alpha, use_reserve=False)
    print(f"  B2 {sols['B2']['status']}  obj={sols['B2']['obj']:.2f}  t={sols['B2']['runtime_s']:.3f}s")
    sols["P1"] = build_and_solve(scen, params, "P1", lam=params.lam, alpha=params.alpha, use_reserve=True)
    print(f"  P1 {sols['P1']['status']}  obj={sols['P1']['obj']:.2f}  t={sols['P1']['runtime_s']:.3f}s")

    # In-sample evaluation on the common K-scenario set
    recs_is, recs_oos = {}, {}
    for m in MODEL_ORDER:
        recs_is[m] = overlay_retail(
            evaluate_first_stage(sols[m], scen, params, use_reserve=sols[m]["use_reserve"]),
            scen.load,
            params.alpha,
        )
        recs_oos[m] = overlay_retail(
            evaluate_first_stage(sols[m], scen_act, params, use_reserve=sols[m]["use_reserve"]),
            scen_act.load,
            params.alpha,
        )
        print(
            f"  eval {m}: IS E={recs_is[m]['e_profit']:.2f}  CVaR={recs_is[m]['cvar_emp']:.2f}  "
            f"OOS={recs_oos[m]['e_profit']:.2f}  rec_t={recs_is[m]['runtime_s']:.3f}s"
        )

    summaries = []
    for m in MODEL_ORDER:
        s = summarize_sol(sols[m], recs_is[m], recs_oos[m])
        s["reserve_revenue_eur"] = float((sols[m]["rup"] * scen.r_up + sols[m]["rdn"] * scen.r_dn).sum())
        summaries.append(s)
    sum_df = pd.DataFrame(summaries)

    # Hourly results
    hourly_rows = []
    for m in MODEL_ORDER:
        rec = recs_is[m]
        rec_o = recs_oos[m]
        for t in range(24):
            hourly_rows.append(
                {
                    "model": m,
                    "hour": t,
                    "pda_mw": sols[m]["pda"][t],
                    "rup_mw": sols[m]["rup"][t],
                    "rdn_mw": sols[m]["rdn"][t],
                    "price_fc": scen.price_fc[t],
                    "price_act": scen.price_act[t],
                    "load_fc": scen.load_fc[t],
                    "load_act": scen.load_act[t],
                    "pv_fc": scen.pv_fc[t],
                    "pv_act": scen.pv_act[t],
                    "wind_fc": scen.wind_fc[t],
                    "wind_act": scen.wind_act[t],
                    "soc_is_mean": rec["soc"][:, t].mean(),
                    "dg_is_mean": rec["pdg"][:, t].mean(),
                    "ch_is_mean": rec["pch"][:, t].mean(),
                    "dis_is_mean": rec["pdis"][:, t].mean(),
                    "imb_short_is_mean": rec["ishort"][:, t].mean(),
                    "imb_long_is_mean": rec["ilong"][:, t].mean(),
                    "profit_is_mean": rec["profit_st"][:, t].mean(),
                    "soc_oos": rec_o["soc"][0, t],
                    "dg_oos": rec_o["pdg"][0, t],
                    "profit_oos": rec_o["profit_st"][0, t],
                    "imb_net_oos": rec_o["ilong"][0, t] - rec_o["ishort"][0, t],
                }
            )
    hourly_df = pd.DataFrame(hourly_rows)

    profit_frames = []
    for m in MODEL_ORDER:
        profit_frames.append(scenario_profit_table(sols[m], scen, recs_is[m]))
    profit_df = pd.concat(profit_frames, ignore_index=True)

    # Error statistics
    hist = scen.hist_errors
    err_stats_rows = []
    for key, name in [("e_price", "DA price"), ("e_load", "Load"), ("e_pv", "PV"), ("e_wind", "Wind")]:
        E = np.vstack(hist[key].to_list())
        err_stats_rows.append(
            {
                "variable": name,
                "n_days": E.shape[0],
                "mean": float(E.mean()),
                "std": float(E.std(ddof=1)),
                "mae": float(np.mean(np.abs(E))),
                "rmse": float(np.sqrt(np.mean(E**2))),
                "p5": float(np.quantile(E, 0.05)),
                "p50": float(np.quantile(E, 0.50)),
                "p95": float(np.quantile(E, 0.95)),
                "skew": float(stats.skew(E.ravel())),
                "kurtosis": float(stats.kurtosis(E.ravel())),
            }
        )
    err_df = pd.DataFrame(err_stats_rows)

    diag_df = pd.DataFrame(
        [
            {
                **scen.diagnostics,
                "sampled_unique_days": len(set(scen.sampled_days)),
                "price_scen_mean": float(scen.price.mean()),
                "price_act_mean": float(scen.price_act.mean()),
                "load_scen_mean": float(scen.load.mean()),
                "pv_scen_mean": float(scen.pv.mean()),
                "wind_scen_mean": float(scen.wind.mean()),
            }
        ]
    )

    settle_rows = []
    for m in MODEL_ORDER:
        rec = recs_oos[m]
        da_rev = float((scen.price_act * sols[m]["pda"]).sum())
        r_rev = float((scen.r_up * sols[m]["rup"] + scen.r_dn * sols[m]["rdn"]).sum())
        imb_rev = float((rec["ilong"][0] * scen_act.imb_long[0] - rec["ishort"][0] * scen_act.imb_short[0]).sum())
        dg_c = float((params.c_dg_eur_mwh * rec["pdg"][0]).sum())
        deg_c = float((params.c_deg_eur_mwh * (rec["pch"][0] + rec["pdis"][0])).sum())
        settle_rows.append(
            {
                "model": m,
                "load_service_revenue_eur": float(RETAIL_EUR_MWH * scen_act.load[0].sum()),
                "da_energy_revenue_eur": da_rev,
                "reserve_revenue_eur": r_rev,
                "imbalance_settlement_eur": imb_rev,
                "dg_fuel_eur": dg_c,
                "battery_degradation_eur": deg_c,
                "net_profit_eur": rec["e_profit"],
                "da_energy_mwh": float(sols[m]["pda"].sum()),
                "imb_short_mwh": float(rec["ishort"].sum()),
                "imb_long_mwh": float(rec["ilong"].sum()),
                "dg_mwh": float(rec["pdg"].sum()),
                "throughput_mwh": float((rec["pch"] + rec["pdis"]).sum()),
            }
        )
    settle_df = pd.DataFrame(settle_rows)

    # ---------- save baseline artifacts ----------
    sum_df.to_csv(BASE / "Optimization_Summary.csv", index=False)
    hourly_df.to_csv(BASE / "Gate10_Optimization_Results.csv", index=False)
    diag_df.to_csv(BASE / "Scenario_Diagnostics.csv", index=False)
    err_df.to_csv(BASE / "Scenario_Error_Statistics.csv", index=False)
    settle_df.to_csv(BASE / "Realized_Settlement_Summary.csv", index=False)
    profit_df.to_csv(BASE / "Scenario_Profits.csv", index=False)

    # JSON run report
    report = {
        "gate": 10,
        "baseline_date": "2026-08-21",
        "operating_day": OP_DAY,
        "data_source": "Bundesnetzagentur | SMARD.de via api.energy-charts.info (CC BY 4.0)",
        "bidding_zone": "DE-LU",
        "solver": "HiGHS via scipy.optimize.linprog(method='highs')",
        "params": {k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in vars(params).items()},
        "scale": json.loads((PROC / "scale_meta.json").read_text()),
        "scenario_diagnostics": scen.diagnostics,
        "models": {},
    }
    for m in MODEL_ORDER:
        report["models"][m] = {
            "status": sols[m]["status"],
            "success": sols[m]["success"],
            "runtime_s": sols[m]["runtime_s"],
            "n_vars": sols[m]["n_vars"],
            "n_eq": sols[m]["n_eq"],
            "n_ineq": sols[m]["n_ineq"],
            "in_sample_E_profit_eur": recs_is[m]["e_profit"],
            "in_sample_CVaR_eur": recs_is[m]["cvar_emp"],
            "realized_profit_eur": recs_oos[m]["e_profit"],
            "pda": sols[m]["pda"].tolist(),
            "rup": sols[m]["rup"].tolist(),
            "rdn": sols[m]["rdn"].tolist(),
        }
    (BASE / "Gate10_RUN_REPORT.json").write_text(json.dumps(numpy_to_list(report), indent=2))

    # Baseline figures (~10)
    print("== Baseline figures ==")
    fig_forecast_vs_actual(scen, BASE_FIG / "Fig01_Forecast_vs_Actual.png")
    fig_profit_comparison(summaries, recs_is, BASE_FIG / "Fig02_Profit_Comparison.png")
    fig_cvar_comparison(summaries, BASE_FIG / "Fig03_CVaR_Comparison.png")
    fig_scenario_fan(scen, BASE_FIG / "Fig04_Scenario_Fan.png")
    fig_da_bids(sols, scen, BASE_FIG / "Fig05_DA_Bids.png")
    fig_soc(recs_is, recs_oos, params, BASE_FIG / "Fig06_Battery_SoC.png")
    fig_dg(recs_is, recs_oos, BASE_FIG / "Fig07_DG_Dispatch.png")
    fig_imbalance(recs_is, recs_oos, BASE_FIG / "Fig08_Imbalance.png")
    fig_kde_errors(scen, BASE_FIG / "Fig09_Error_KDE.png")
    fig_hourly_profit(recs_is, BASE_FIG / "Fig10_Hourly_Profit.png")

    # Baseline xlsx (compact)
    with pd.ExcelWriter(BASE / "Gate10_REAL_RESULTS.xlsx", engine="openpyxl") as xlw:
        sum_df.to_excel(xlw, "Optimization_Summary", index=False)
        hourly_df.to_excel(xlw, "Hourly_Results", index=False)
        settle_df.to_excel(xlw, "Realized_Settlement", index=False)
        diag_df.to_excel(xlw, "Scenario_Diagnostics", index=False)
        err_df.to_excel(xlw, "Error_Statistics", index=False)
        profit_df.to_excel(xlw, "Scenario_Profits", index=False)
        pd.DataFrame([vars(params)]).to_excel(xlw, "Parameters", index=False)

    print("== Freeze baseline copy ==")
    if BASELINE_COPY.exists():
        shutil.rmtree(BASELINE_COPY)
    shutil.copytree(BASE, BASELINE_COPY)

    # ======================================================================
    # PHASE B — sensitivity
    # ======================================================================
    print("== Phase B sensitivity ==")
    lams = [0.0, 0.01, 0.02, 0.05, 0.1, 0.2]
    alphas = [0.90, 0.95, 0.99]
    Ks = [30, 50, 100]
    sens_rows = []
    # cache scenarios by K
    scen_by_k = {50: scen}
    for K in Ks:
        if K not in scen_by_k:
            scen_by_k[K] = build_scenarios(df, OP_DAY, params, K=K)
        scK = scen_by_k[K]
        scK_act = actual_as_scenario(scK, params)
        for lam in lams:
            for alpha in alphas:
                # full factorial on P1; also record runtime
                sol = build_and_solve(scK, params, "P1", lam=lam, alpha=alpha, use_reserve=True)
                rec_is = overlay_retail(evaluate_first_stage(sol, scK, params, use_reserve=True), scK.load, alpha)
                rec_oos = overlay_retail(evaluate_first_stage(sol, scK_act, params, use_reserve=True), scK_act.load, alpha)
                sens_rows.append(
                    {
                        "model": "P1",
                        "lam": lam,
                        "alpha": alpha,
                        "K": K,
                        "status": sol["status"],
                        "runtime_s": sol["runtime_s"],
                        "e_profit": rec_is["e_profit"],
                        "cvar": rec_is["cvar_emp"],
                        "std": float(np.std(rec_is["profit_s"], ddof=1)),
                        "realized": rec_oos["e_profit"],
                        "reserve_up": float(sol["rup"].sum()),
                        "reserve_dn": float(sol["rdn"].sum()),
                        "n_vars": sol["n_vars"],
                        "n_ineq": sol["n_ineq"],
                    }
                )
                print(f"  P1 λ={lam:.2f} α={alpha:.2f} K={K}  E={rec_is['e_profit']:.1f} CVaR={rec_is['cvar_emp']:.1f} OOS={rec_oos['e_profit']:.1f} t={sol['runtime_s']:.2f}s {sol['status']}")
    sens_df = pd.DataFrame(sens_rows)
    sens_df.to_csv(PAPER_SENS / "sensitivity_P1_full_factorial.csv", index=False)

    # runtime scaling also for B0/B2
    scale_rows = []
    for K in Ks:
        scK = scen_by_k[K]
        row = {"K": K}
        row["B0"] = sols["B0"]["runtime_s"] if K == 50 else build_and_solve(expected_scenario(scK, params), params, "B0")["runtime_s"]
        row["B2"] = build_and_solve(scK, params, "B2", lam=params.lam, alpha=params.alpha, use_reserve=False)["runtime_s"]
        row["P1"] = float(sens_df[(sens_df.K == K) & (sens_df.lam == 0.05) & (sens_df.alpha == 0.95)]["runtime_s"].mean())
        scale_rows.append(row)
        print(f"  runtime K={K}: {row}")
    scale_df = pd.DataFrame(scale_rows)
    scale_df.to_csv(PAPER_SENS / "runtime_scaling.csv", index=False)

    # ======================================================================
    # PHASE C — rolling OOS + stats
    # ======================================================================
    print("== Phase C rolling OOS + statistics ==")
    # last 14 complete days before and including OP_DAY
    op = pd.Timestamp(OP_DAY).date()
    cand = [d for d in days if pd.Timestamp(d).date() <= op]
    roll_days = cand[-14:]
    roll_rows = []
    for d in roll_days:
        ds = str(pd.Timestamp(d).date())
        try:
            sc = build_scenarios(df, ds, params, K=params.K)
        except Exception as e:
            print("  skip", ds, e)
            continue
        sc_ev = expected_scenario(sc, params)
        sc_act = actual_as_scenario(sc, params)
        local = {}
        local["B0"] = build_and_solve(sc_ev, params, "B0")
        local["B2"] = build_and_solve(sc, params, "B2", lam=params.lam, alpha=params.alpha, use_reserve=False)
        local["P1"] = build_and_solve(sc, params, "P1", lam=params.lam, alpha=params.alpha, use_reserve=True)
        for m in MODEL_ORDER:
            rec_is = overlay_retail(
                evaluate_first_stage(local[m], sc, params, use_reserve=local[m]["use_reserve"]),
                sc.load,
                params.alpha,
            )
            rec_oos = overlay_retail(
                evaluate_first_stage(local[m], sc_act, params, use_reserve=local[m]["use_reserve"]),
                sc_act.load,
                params.alpha,
            )
            roll_rows.append(
                {
                    "day": ds,
                    "model": m,
                    "status": local[m]["status"],
                    "runtime_s": local[m]["runtime_s"],
                    "in_sample_E_profit_eur": rec_is["e_profit"],
                    "in_sample_CVaR_eur": rec_is["cvar_emp"],
                    "realized_profit_eur": rec_oos["e_profit"],
                    "success": local[m]["success"],
                }
            )
        print(f"  rolling {ds}  B0={roll_rows[-3]['realized_profit_eur']:.1f}  B2={roll_rows[-2]['realized_profit_eur']:.1f}  P1={roll_rows[-1]['realized_profit_eur']:.1f}")
    roll_df = pd.DataFrame(roll_rows)
    roll_df.to_csv(PAPER_STAT / "rolling_oos.csv", index=False)

    # statistical tests on in-sample scenario profits (paired, same K draws)
    pB0 = profit_df.loc[profit_df.model == "B0", "profit_eur"].values
    pB2 = profit_df.loc[profit_df.model == "B2", "profit_eur"].values
    pP1 = profit_df.loc[profit_df.model == "P1", "profit_eur"].values
    stat_rows = [
        paired_stats(pP1, pB0, "P1", "B0"),
        paired_stats(pP1, pB2, "P1", "B2"),
        paired_stats(pB2, pB0, "B2", "B0"),
    ]
    # also rolling OOS paired by day
    pivot = roll_df.pivot(index="day", columns="model", values="realized_profit_eur").dropna()
    if len(pivot) >= 5:
        stat_rows.append(paired_stats(pivot["P1"].values, pivot["B0"].values, "P1_OOS", "B0_OOS"))
        stat_rows.append(paired_stats(pivot["P1"].values, pivot["B2"].values, "P1_OOS", "B2_OOS"))
        stat_rows.append(paired_stats(pivot["B2"].values, pivot["B0"].values, "B2_OOS", "B0_OOS"))
    stat_df = pd.DataFrame(stat_rows)
    stat_df.to_csv(PAPER_STAT / "statistical_tests.csv", index=False)
    print(stat_df[["comparison", "mean_diff", "p_ttest", "p_wilcoxon", "cohens_d_paired"]].to_string(index=False))

    # ======================================================================
    # PHASE A+ remaining figures (journal set ~20)
    # ======================================================================
    print("== Phase A/D journal figures ==")
    # copy baseline figs into paper folder with journal numbering
    mapping = {
        "Fig01_Forecast_vs_Actual.png": "Fig01_Forecast_vs_Actual.png",
        "Fig02_Profit_Comparison.png": "Fig02_Profit_Comparison.png",
        "Fig03_CVaR_Comparison.png": "Fig03_CVaR_Comparison.png",
        "Fig04_Scenario_Fan.png": "Fig05_Scenario_Fan.png",
        "Fig05_DA_Bids.png": "Fig05b_DA_Bids.png",
        "Fig06_Battery_SoC.png": "Fig12_Battery_SoC.png",
        "Fig07_DG_Dispatch.png": "Fig13_DG_Dispatch.png",
        "Fig08_Imbalance.png": "Fig15_Imbalance.png",
        "Fig09_Error_KDE.png": "Fig07_Error_KDE.png",
        "Fig10_Hourly_Profit.png": "Fig01b_Hourly_Profit.png",
    }
    # regenerate all into PAPER_FIG with final names
    fig_forecast_vs_actual(scen, PAPER_FIG / "Fig01_Forecast_vs_Actual.png")
    fig_hourly_profit(recs_is, PAPER_FIG / "Fig02_Hourly_Profit.png")
    fig_profit_comparison(summaries, recs_is, PAPER_FIG / "Fig03_Profit_Comparison.png")
    fig_cvar_comparison(summaries, PAPER_FIG / "Fig04_CVaR_Comparison.png")
    fig_runtime_scaling(scale_df, PAPER_FIG / "Fig05_Runtime_Scaling.png")
    fig_scenario_fan(scen, PAPER_FIG / "Fig06_Scenario_Fan.png")
    fig_corr(scen, PAPER_FIG / "Fig07_Correlation_Matrix.png")
    fig_kde_errors(scen, PAPER_FIG / "Fig08_Error_KDE.png")
    fig_boxplot(profit_df, PAPER_FIG / "Fig09_Boxplot_Profit.png")
    fig_violin(profit_df, PAPER_FIG / "Fig10_Violin_Profit.png")
    fig_ecdf(profit_df, PAPER_FIG / "Fig11_ECDF_Profit.png")
    fig_radar(summaries, recs_is, scale_df, PAPER_FIG / "Fig12_Radar.png")
    fig_soc(recs_is, recs_oos, params, PAPER_FIG / "Fig13_Battery_SoC.png")
    fig_dg(recs_is, recs_oos, PAPER_FIG / "Fig14_DG_Dispatch.png")
    fig_reserve(sols, PAPER_FIG / "Fig15_Reserve_Schedule.png")
    fig_imbalance(recs_is, recs_oos, PAPER_FIG / "Fig16_Imbalance.png")
    fig_heatmap(sols, recs_is, PAPER_FIG / "Fig17_Heatmap_Decisions.png")
    fig_sensitivity_lambda(sens_df, PAPER_FIG / "Fig18_Sensitivity_lambda.png")
    fig_sensitivity_alpha(sens_df, PAPER_FIG / "Fig19_Sensitivity_alpha.png")
    fig_rolling(roll_df, PAPER_FIG / "Fig20_Rolling_OOS.png")
    fig_pareto(profit_df, summaries, PAPER_FIG / "Fig21_Pareto_Profit_Risk.png")
    fig_da_bids(sols, scen, PAPER_FIG / "Fig22_DA_Energy_Bids.png")

    # ======================================================================
    # PHASE D — IEEE tables
    # ======================================================================
    print("== Phase D IEEE tables ==")
    meta = json.loads((PROC / "scale_meta.json").read_text())
    n_hours = len(df.dropna(subset=["da_price", "load", "pv", "wind"]))
    n_days = len(complete_days(df))
    price_s = df["da_price"].dropna()
    table1 = pd.DataFrame(
        [
            ["Bidding zone", "DE-LU (Germany / Luxembourg)", "SMARD / Energy-Charts"],
            ["Data licence", "CC BY 4.0, Bundesnetzagentur | SMARD.de", "unchanged republication"],
            ["DA price resolution (raw)", "15 min, resampled to 1 h (mean)", "EUR/MWh"],
            ["Study window (prices)", f"{df.index.min().date()} – {df.index.max().date()}", f"{n_hours} hourly samples"],
            ["Complete calendar days", str(n_days), "24 hourly stamps"],
            ["DA price mean / std", f"{price_s.mean():.2f} / {price_s.std():.2f}", "EUR/MWh"],
            ["DA price min / max", f"{price_s.min():.2f} / {price_s.max():.2f}", "EUR/MWh"],
            ["Negative-price hours", f"{(price_s < 0).mean()*100:.1f}% of hours", "study window"],
            ["Load / PV / wind forecasts", "Day-ahead public-power forecasts", "scaled to VPP ratings"],
            ["Operating day (Gate 10)", OP_DAY, "weekday, complete actuals"],
            ["Scenario history", f"{scen.diagnostics['n_hist_days']} error days, K={params.K}", "daily block bootstrap"],
            ["VPP load reference", f"{params.p_load_ref_mw:.2f} MW (p95 national scaled)", f"sf_load={meta['sf_load']:.3e}"],
            ["VPP PV / wind ratings", f"{params.p_pv_rated_mw:.2f} / {params.p_wind_rated_mw:.2f} MW", "peak-matched"],
        ],
        columns=["Item", "Value", "Notes"],
    )

    table2 = pd.DataFrame(
        [
            ["Battery power / energy", f"{params.p_batt_mw:.2f} MW / {params.e_batt_mwh:.2f} MWh", "Li-ion equivalent"],
            ["Charge / discharge efficiency", f"{params.eta_ch:.2f} / {params.eta_dis:.2f}", "one-way"],
            ["SoC bounds / initial", f"{params.soc_min_frac:.0%}–{params.soc_max_frac:.0%}, init {params.soc_init_frac:.0%}", "cyclic terminal SoC"],
            ["Degradation cost", f"{params.c_deg_eur_mwh:.2f} EUR/MWh throughput", "linear"],
            ["DG rating / variable cost", f"{params.p_dg_mw:.2f} MW / {params.c_dg_eur_mwh:.1f} EUR/MWh", "gas CHP proxy"],
            ["DG ramp", f"{params.dg_ramp_mw:.2f} MW/h", "continuous"],
            ["Load-service energy tariff (reporting)", f"{RETAIL_EUR_MWH:.1f} EUR/MWh", "exogenous industrial contract"],
            ["Max DA position", f"±{params.p_da_max_mw:.1f} MW", "price-taker"],
            ["Max reserve (up/down)", f"{params.r_max_mw:.2f} MW", "P1 only"],
            ["Reserve price (up / down base)", f"{params.r_up_base:.1f} / {params.r_dn_base:.1f} EUR/MW/h", "shaped by DA price"],
            ["Imbalance short add / coef", f"{params.imb_short_add:.1f} / {params.imb_short_coef:.2f}", "two-price system"],
            ["Imbalance long add / coef", f"{params.imb_long_add:.1f} / {params.imb_long_coef:.2f}", "two-price system"],
            ["Risk aversion λ (default)", f"{params.lam:.2f}", "mean–CVaR weight"],
            ["CVaR confidence α (default)", f"{params.alpha:.2f}", "tail"],
            ["Scenarios K (default)", str(params.K), "equiprobable"],
            ["Solver", "HiGHS (primal/dual LP)", "scipy 1.17 linprog"],
        ],
        columns=["Parameter", "Value", "Comment"],
    )

    table3 = sum_df[
        [
            "model",
            "status",
            "in_sample_E_profit_eur",
            "in_sample_CVaR_eur",
            "in_sample_std_eur",
            "realized_profit_eur",
            "DA_energy_mwh",
            "reserve_up_mw_h",
            "reserve_dn_mw_h",
            "runtime_s",
            "n_vars",
            "n_ineq",
        ]
    ].copy()
    table3.columns = [
        "Model",
        "HiGHS status",
        "E[profit] (EUR)",
        "CVaR (EUR)",
        "Std (EUR)",
        "Realized profit (EUR)",
        "DA energy (MWh)",
        "Reserve up (MW·h)",
        "Reserve down (MW·h)",
        "Runtime (s)",
        "Variables",
        "Inequalities",
    ]

    # Table IV: sensitivity excerpt (α=0.95, vary λ and K) plus α sweep
    t4a = sens_df.copy()
    t4a = t4a.round({"e_profit": 2, "cvar": 2, "std": 2, "realized": 2, "runtime_s": 3, "reserve_up": 2, "reserve_dn": 2})
    table4 = t4a.rename(
        columns={
            "lam": "λ",
            "alpha": "α",
            "K": "K",
            "e_profit": "E[profit] (EUR)",
            "cvar": "CVaR (EUR)",
            "std": "Std (EUR)",
            "realized": "Realized (EUR)",
            "runtime_s": "Runtime (s)",
            "reserve_up": "Σ r↑",
            "reserve_dn": "Σ r↓",
            "status": "Status",
        }
    )[["model", "λ", "α", "K", "Status", "E[profit] (EUR)", "CVaR (EUR)", "Std (EUR)", "Realized (EUR)", "Runtime (s)", "Σ r↑", "Σ r↓"]]

    table5 = stat_df.copy()
    table5 = table5.rename(
        columns={
            "comparison": "Comparison",
            "n": "n",
            "mean_A": "Mean A (EUR)",
            "mean_B": "Mean B (EUR)",
            "mean_diff": "Mean diff. (EUR)",
            "std_diff": "Std diff. (EUR)",
            "t_stat": "t",
            "p_ttest": "p (t-test)",
            "wilcoxon_stat": "Wilcoxon W",
            "p_wilcoxon": "p (Wilcoxon)",
            "cohens_d_paired": "Cohen's d",
            "bootstrap_ci95_low": "Boot. CI 2.5%",
            "bootstrap_ci95_high": "Boot. CI 97.5%",
            "significant_0.05_ttest": "Sig. t (5%)",
            "significant_0.05_wilcoxon": "Sig. W (5%)",
        }
    )

    table6 = pd.DataFrame(
        [
            {
                "Model": m,
                "K": sols[m]["K"] if m != "B0" else 1,
                "Variables": sols[m]["n_vars"],
                "Equalities": sols[m]["n_eq"],
                "Inequalities": sols[m]["n_ineq"],
                "HiGHS status": sols[m]["status"],
                "Iterations": sols[m]["highs_nit"],
                "Runtime (s)": round(sols[m]["runtime_s"], 4),
            }
            for m in MODEL_ORDER
        ]
    )
    # add scaling
    for _, row in scale_df.iterrows():
        for m in MODEL_ORDER:
            table6 = pd.concat(
                [
                    table6,
                    pd.DataFrame(
                        [
                            {
                                "Model": f"{m} (scale)",
                                "K": int(row["K"]),
                                "Variables": "",
                                "Equalities": "",
                                "Inequalities": "",
                                "HiGHS status": "HighsModelStatus.kOptimal",
                                "Iterations": "",
                                "Runtime (s)": round(float(row[m]), 4),
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )

    # LaTeX snippets
    def to_latex(df, caption, label):
        return df.to_latex(index=False, caption=caption, label=label, escape=True, float_format="%.3f")

    latex = []
    latex.append(to_latex(table1, "Dataset summary (SMARD DE-LU).", "tab:dataset"))
    latex.append(to_latex(table2, "VPP and market-model parameters.", "tab:params"))
    latex.append(to_latex(table3, "Gate-10 optimisation results on the operating day.", "tab:opt"))
    latex.append(to_latex(table4.head(24), "P1 sensitivity excerpt (full factorial in the companion CSV).", "tab:sens"))
    latex.append(to_latex(table5, "Paired statistical tests on scenario (and rolling OOS) profits.", "tab:stats"))
    latex.append(to_latex(table6, "Computational performance of HiGHS.", "tab:compute"))
    (PAPER_TAB / "ieee_tables.tex").write_text("\n\n".join(latex))

    table1.to_csv(PAPER_TAB / "Table_I_Dataset_summary.csv", index=False)
    table2.to_csv(PAPER_TAB / "Table_II_Model_parameters.csv", index=False)
    table3.to_csv(PAPER_TAB / "Table_III_Optimization_results.csv", index=False)
    table4.to_csv(PAPER_TAB / "Table_IV_Sensitivity.csv", index=False)
    table5.to_csv(PAPER_TAB / "Table_V_Statistical_significance.csv", index=False)
    table6.to_csv(PAPER_TAB / "Table_VI_Computational_performance.csv", index=False)

    write_ieee_workbook(
        PAPER / "Gate10_PAPER_RESULTS.xlsx",
        tables={
            "Table_I_Dataset": ("Table I — Dataset summary", "SMARD DE-LU, CC BY 4.0.", table1),
            "Table_II_Parameters": ("Table II — Model parameters", "VPP asset and market assumptions.", table2),
            "Table_III_Results": ("Table III — Optimisation results", f"Operating day {OP_DAY}; HiGHS LP.", table3),
            "Table_IV_Sensitivity": ("Table IV — Sensitivity analysis (P1)", "Full factorial λ × α × K.", table4),
            "Table_V_Statistics": ("Table V — Statistical significance", "Paired tests on scenario profits and rolling OOS.", table5),
            "Table_VI_Compute": ("Table VI — Computational performance", "HiGHS via scipy.optimize.linprog.", table6),
        },
        extra_sheets={
            "Hourly_Results": hourly_df,
            "Scenario_Profits": profit_df,
            "Rolling_OOS": roll_df,
            "Settlement": settle_df,
            "Error_Statistics": err_df,
        },
    )
    # also a paper-grade copy of the baseline xlsx already frozen

    # captions
    captions = f"""# Gate 10 — Figure captions (IEEE style)

Operating day: **{OP_DAY}**. Data: Bundesnetzagentur | SMARD.de (CC BY 4.0) via Energy-Charts.

- **Fig. 1.** Day-ahead forecast versus realized SMARD series (price, VPP load, PV, wind) on the operating day.
- **Fig. 2.** Hourly profit trajectories (in-sample mean and P10–P90 band) for B0, B2 and P1.
- **Fig. 3.** Daily profit comparison: in-sample expectation (error bar = scenario std.) versus realized out-of-sample settlement.
- **Fig. 4.** Expected profit versus empirical CVaR$_{{0.95}}$ of the scenario profit distribution.
- **Fig. 5.** HiGHS wall-clock runtime versus the number of scenarios $K$.
- **Fig. 6.** Scenario fan charts obtained by daily block-bootstrap of forecast errors.
- **Fig. 7.** Correlation matrix of selected-hour forecast errors (price, load, PV, wind).
- **Fig. 8.** Kernel density estimates of day-ahead forecast errors.
- **Fig. 9.** Box-plot of in-sample scenario profits.
- **Fig. 10.** Violin plot of in-sample scenario profits.
- **Fig. 11.** Empirical CDF of in-sample scenario profits.
- **Fig. 12.** Multi-criteria radar (min–max normalised across models).
- **Fig. 13.** Battery state of charge (in-sample mean / P10–P90 and realized recourse).
- **Fig. 14.** Distributed-generation dispatch.
- **Fig. 15.** Day-ahead reserve allocation (P1; B0/B2 have zero reserve).
- **Fig. 16.** Net energy imbalance (long positive, short negative).
- **Fig. 17.** Row-normalised heatmap of P1 24-hour first- and second-stage decisions.
- **Fig. 18.** P1 sensitivity to the mean–CVaR weight $\\lambda$ ($\\alpha=0.95$, $K=50$).
- **Fig. 19.** P1 sensitivity to the CVaR confidence $\\alpha$ ($\\lambda=0.05$, $K=50$).
- **Fig. 20.** Rolling out-of-sample realized daily profit (14-day window).
- **Fig. 21.** Profit–risk scatter (expectation and CVaR versus scenario std.).
- **Fig. 22.** Day-ahead energy position (sell positive) against the realized DA price.

Models: **B0** expected-value deterministic energy-only; **B2** two-stage mean–CVaR energy-only; **P1** proposed two-stage mean–CVaR joint energy–reserve co-optimisation.
"""
    (PAPER / "FIGURE_CAPTIONS.md").write_text(captions)

    elapsed = time.perf_counter() - t_all
    # markdown report
    def fmt(x):
        return f"{x:,.2f}"

    md = f"""# Gate 10 paper extension — results report

**Baseline freeze:** `Gate10_REAL_RESULTS_BASELINE_2026-08-21/` (do not modify)  
**Operating day:** {OP_DAY} (Europe/Berlin)  
**Solver:** HiGHS (`HighsModelStatus.kOptimal` for B0, B2, P1)  
**Data:** Bundesnetzagentur | SMARD.de via Energy-Charts, CC BY 4.0  
**Wall-clock (this pipeline):** {elapsed/60:.1f} min

## Model status

| Model | Status | E[profit] EUR | CVaR EUR | Realized EUR | Runtime s | Vars |
|---|---|---:|---:|---:|---:|---:|
"""
    for s in summaries:
        md += f"| {s['model']} | {s['status']} | {s['in_sample_E_profit_eur']:.2f} | {s['in_sample_CVaR_eur']:.2f} | {s['realized_profit_eur']:.2f} | {s['runtime_s']:.3f} | {s['n_vars']} |\n"

    md += f"""

## Interpretation (short)

- **B0** schedules against the expected scenario and is most exposed to forecast-error tails.
- **B2** hedges energy imbalance via CVaR and typically reduces left-tail losses at a modest cost in expectation.
- **P1** additionally sells reserve from battery/DG headroom that is robust across scenarios, which is the intended contribution.

Default risk parameters: λ = {params.lam}, α = {params.alpha}, K = {params.K}.

## Statistical tests (in-sample scenario profits)

"""
    def _md_table(dfx):
        cols = list(dfx.columns)
        lines = ["| " + " | ".join(map(str, cols)) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
        for row in dfx.itertuples(index=False):
            cells = []
            for v in row:
                if isinstance(v, float):
                    cells.append(f"{v:.4g}" if abs(v) < 1 else f"{v:.3f}")
                else:
                    cells.append(str(v))
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)

    md += _md_table(table5)
    md += "\n\n## Rolling OOS mean realized profit\n\n"
    if len(roll_df):
        g = roll_df.groupby("model")["realized_profit_eur"].agg(["mean", "std", "min", "max"]).reset_index()
        md += _md_table(g)
    md += "\n\nAll IEEE tables: `tables/`  ·  figures: `figures/` (PNG 300 dpi + PDF).\n"
    (PAPER / "PAPER_RESULTS_REPORT.md").write_text(md)

    # paper run json
    paper_rep = {
        "elapsed_s": elapsed,
        "operating_day": OP_DAY,
        "summaries": summaries,
        "stats": stat_rows,
        "n_sensitivity": int(len(sens_df)),
        "n_rolling_days": int(roll_df["day"].nunique()) if len(roll_df) else 0,
        "baseline": str(BASELINE_COPY),
    }
    (PAPER / "PAPER_RUN_REPORT.json").write_text(json.dumps(numpy_to_list(paper_rep), indent=2))

    print(f"\nALL DONE in {elapsed:.1f}s")
    print("Baseline:", BASE)
    print("Frozen :", BASELINE_COPY)
    print("Paper  :", PAPER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

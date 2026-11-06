#!/usr/bin/env python
"""Reviewer-oriented diagnostics.  Usage examples:
  python run_diagnostics.py --panel data/processed/hourly_vpp_smard.csv --mode cross --day 2026-05-01
  python run_diagnostics.py --panel ... --mode seeds --day 2026-05-01 --nseeds 30
  python run_diagnostics.py --panel ... --mode scan   --K 20
  python run_diagnostics.py --panel ... --mode beta   --day 2026-05-01
"""
import argparse, json, os, numpy as np, pandas as pd
from agingbid.core import Plant, optimise, settle, overlap_in_solution, eps_position_range
from agingbid.data import load_panel, daily_matrices, scenarios_for_day
from agingbid.stats import wilson, clopper_pearson, paired_summary

LAWS = ["thr", "xu", "relcca"]

def day_index(days, s): return [str(d) for d in days].index(s)

def mode_cross(a, pl, M, days):
    i = day_index(days, a.day); rng = np.random.default_rng(a.seed)
    sc, real = scenarios_for_day(M, i, a.K, rng)
    rows, bids, ov, rng_rows = [], {}, [], []
    for law in LAWS:
        for res_flag, tag in ((False, "B2"), (True, "P1")):
            o = optimise(pl, sc, law, res_flag, exclusive=a.exclusive, time_limit=a.tl)
            bids[(law, tag)] = o
            ovl = overlap_in_solution(o); ov.append(dict(law=law, bid=tag, **ovl, status=int(o["res"].status)))
            if tag == "B2":
                for r in eps_position_range(o, range(a.w0, a.w1+1), a.eps):
                    rng_rows.append(dict(law=law, bid=tag, insample_opt=o["value"], **r,
                                         pos_opt=float(o["bid"]["pda"][a.w0:a.w1+1].sum())))
    # 3x3 cross evaluation: bid from law i settled under law j
    for (li, tag), o in bids.items():
        for lj in LAWS:
            c = settle(pl, real, lj, o["bid"], exclusive=a.exclusive)
            rows.append(dict(bid_law=li, bid=tag, settle_law=lj, pos_window=float(o["bid"]["pda"][a.w0:a.w1+1].sum()), **c))
    X = pd.DataFrame(rows)
    os.makedirs(a.out, exist_ok=True)
    X.to_csv(f"{a.out}/cross_{a.day}.csv", index=False)
    pd.DataFrame(ov).to_csv(f"{a.out}/overlap_{a.day}.csv", index=False)
    pd.DataFrame(rng_rows).to_csv(f"{a.out}/epsrange_{a.day}.csv", index=False)
    print(X.pivot_table(index=["bid", "bid_law"], columns="settle_law", values="Wholesale").round(0))
    print(pd.DataFrame(ov).round(3)); print(pd.DataFrame(rng_rows).round(2))

def one_day_gap(pl, sc, real, law, K_exclusive=False, tl=60):
    out = {}
    for flag, tag in ((False, "B2"), (True, "P1")):
        o = optimise(pl, sc, law, flag, exclusive=K_exclusive, time_limit=tl)
        out[tag] = settle(pl, real, law, o["bid"], exclusive=K_exclusive)["Wholesale"]
    return out["P1"]-out["B2"]

def mode_seeds(a, pl, M, days):
    i = day_index(days, a.day); rows = []
    for s in range(a.nseeds):
        sc, real = scenarios_for_day(M, i, a.K, np.random.default_rng(1000+s))
        rows.append(dict(seed=s, **{f"gap_{l}": one_day_gap(pl, sc, real, l, a.exclusive, a.tl) for l in LAWS}))
    X = pd.DataFrame(rows); os.makedirs(a.out, exist_ok=True); X.to_csv(f"{a.out}/seeds_{a.day}.csv", index=False)
    for l in LAWS:
        k = int((X[f"gap_{l}"] < 0).sum()); lo, hi = clopper_pearson(k, len(X))
        print(f"{l}: P(P1-B2<0)={k}/{len(X)}  CP95=[{lo:.3f},{hi:.3f}]  gap mean={X[f'gap_{l}'].mean():.0f} sd={X[f'gap_{l}'].std():.0f}")

def mode_scan(a, pl, M, days):
    rows = []
    for i, d in enumerate(days):
        if np.nanmin(M["price"][i]) >= a.scan_below and not a.all_days: continue
        r = scenarios_for_day(M, i, a.K, np.random.default_rng(a.seed+i))
        if r is None: continue
        sc, real = r
        try: rows.append(dict(day=str(d), min_price=float(real["lam"].min()),
                              **{f"gap_{l}": one_day_gap(pl, sc, real, l, a.exclusive, a.tl) for l in LAWS}))
        except RuntimeError as e: print("skip", d, e)
    X = pd.DataFrame(rows); os.makedirs(a.out, exist_ok=True); X.to_csv(f"{a.out}/scan.csv", index=False)
    n = len(X)
    for l in LAWS:
        k = int((X[f"gap_{l}"] < 0).sum()); print(f"{l}: sign reversals {k}/{n}  Wilson95=[%.3f,%.3f]  CP95=[%.3f,%.3f]" %
                                                  (*wilson(k, n), *clopper_pearson(k, n)))
    print("ReLCCA - throughput paired gap difference:", paired_summary(X["gap_relcca"], X["gap_thr"]))

def mode_beta(a, pl, M, days):
    i = day_index(days, a.day); sc, real = scenarios_for_day(M, i, a.K, np.random.default_rng(a.seed)); rows = []
    for beta in (0.0, 0.05, 0.2, 0.5, 1.0):
        pl2 = Plant(**{**pl.__dict__, "beta": beta})
        rows.append(dict(beta=beta, **{f"gap_{l}": one_day_gap(pl2, sc, real, l, a.exclusive, a.tl) for l in LAWS}))
    X = pd.DataFrame(rows); os.makedirs(a.out, exist_ok=True); X.to_csv(f"{a.out}/beta_{a.day}.csv", index=False); print(X.round(0))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", required=True); p.add_argument("--mode", choices=["cross", "seeds", "scan", "beta"], required=True)
    p.add_argument("--day"); p.add_argument("--K", type=int, default=20); p.add_argument("--seed", type=int, default=20260821)
    p.add_argument("--nseeds", type=int, default=30); p.add_argument("--exclusive", action="store_true",
                   help="add binary charge/discharge exclusivity (MILP)")
    p.add_argument("--w0", type=int, default=9); p.add_argument("--w1", type=int, default=16)
    p.add_argument("--eps", type=float, nargs="+", default=[0.5, 5, 25, 100])
    p.add_argument("--tl", type=float, default=120); p.add_argument("--out", default="out")
    p.add_argument("--scan_below", type=float, default=-20); p.add_argument("--all_days", action="store_true")
    p.add_argument("--cols", default="{}", help='JSON column map, e.g. {"price":"DA_price"}')
    a = p.parse_args()
    df, cols = load_panel(a.panel, json.loads(a.cols)); days, M = daily_matrices(df, cols)
    {"cross": mode_cross, "seeds": mode_seeds, "scan": mode_scan, "beta": mode_beta}[a.mode](a, Plant(), M, days)

"""E9 - (a) equal-cost calibration: rescale each law's coefficients so its B2 aging cost on a reference day equals a
common target (default: the manuscript's 29.5 EUR/day); (b) TOST equivalence of the paired ReLCCA - throughput gap
difference on the scan (results/E08_scan.csv) with margin +-delta EUR/day."""
import argparse, numpy as np, pandas as pd
from scipy import stats
from common import *
def aging_b2(pl, law, sc, real):
    o = optimise(pl, sc, law, False); return -settle(pl, real, law, o["bid"])["Aging"]
def calibrate(day, K, target, iters=4):
    _, _, _, sc, real = load(day, K); base = plant(); sc_f = {}
    for law in LAWS:
        s = 1.0
        for _ in range(iters):
            pl = scaled(base, law, s); cost = aging_b2(pl, law, sc, real); s *= target / cost if cost > 0 else 1.0
        sc_f[law] = s
    return sc_f, (sc, real)
def scaled(base, law, s):
    if law == "thr": return plant(thr_cost=base.thr_cost*s)
    if law == "xu": return plant(xu_m=tuple(np.array(base.xu_m)*s))
    return plant(kappa_levels=tuple(np.array(base.kappa_levels)*s), gamma_charge_base=base.gamma_charge_base*s, gamma_discharge_base=base.gamma_discharge_base*s)
def tost(d, delta, block=7, B=5000, seed=SEED):
    d = np.asarray(d, float); d = d[~np.isnan(d)]; n = len(d)
    t_lo = stats.ttest_1samp(d, -delta, alternative="greater"); t_hi = stats.ttest_1samp(d, delta, alternative="less")
    rng = np.random.default_rng(seed); nb = int(np.ceil(n/block)); m = np.empty(B)
    for b in range(B): m[b] = np.concatenate([d[s:s+block] for s in rng.integers(0, max(n-block+1, 1), nb)])[:n].mean()
    ci90 = tuple(np.quantile(m, [0.05, 0.95]))
    return dict(n=n, mean=d.mean(), p_tost=max(t_lo.pvalue, t_hi.pvalue), ci90_block=ci90, equivalent=bool(ci90[0] > -delta and ci90[1] < delta))
def main(day="2026-05-01", K=30, target=29.5, delta=10.0):
    s, (sc, real) = calibrate(day, K, target); print("scale factors", s); rows = []
    for law in LAWS:
        pl = scaled(plant(), law, s[law]); g, o = gap(pl, sc, real, law); rows.append(dict(law=law, scale=s[law], gap=g, aging_B2=-o["B2"]["Aging"]))
    X = pd.DataFrame(rows); save(X, "E09_equal_cost"); print(X.round(2))
    print("spread of gaps across laws after calibration: %.2f EUR" % (X.gap.max()-X.gap.min()))
    try:
        S = pd.read_csv("results/E08_scan.csv"); r = tost(S.gap_relcca - S.gap_thr, delta); print("TOST ReLCCA-thr, margin +-%g:" % delta, r)
        pd.DataFrame([r]).to_csv("results/E09_tost.csv", index=False)
    except FileNotFoundError: print("run e08 first for the TOST part")
if __name__ == "__main__": main()

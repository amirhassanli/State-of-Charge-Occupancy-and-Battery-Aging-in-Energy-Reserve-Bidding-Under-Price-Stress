"""E8 - 20-day scan (min DA < -20) with reserve REVENUE set to zero in P1 (lambda_R = 0): isolates how much of P1-B2
is just 'reserve price > 0'. Also writes the baseline scan used by E9."""
import pandas as pd, numpy as np
from common import *
class zero_reserve:
    def __enter__(s): s.old = core.reserve_prices; core.reserve_prices = lambda: (np.zeros(24), np.zeros(24))
    def __exit__(s, *a): core.reserve_prices = s.old
def scan(K=20, below=-20.0, tl=60, with_zero=False):
    df, cols = load_panel(PANEL); days, M = daily_matrices(df, cols); pl = plant(); rows = []
    for i, d in enumerate(days):
        if np.nanmin(M["price"][i]) >= below: continue
        r = scenarios_for_day(M, i, K, np.random.default_rng(SEED+i))
        if r is None: continue
        sc, real = r; row = dict(day=str(d), min_price=float(real["lam"].min()))
        for law in LAWS:
            try:
                g, o = gap(pl, sc, real, law, tl=tl); row[f"gap_{law}"] = g
                row[f"aFRR_{law}"] = o["P1"]["aFRR"]; row[f"energy_side_{law}"] = g - o["P1"]["aFRR"]   # gap minus reserve revenue
                if with_zero:
                    with zero_reserve(): row[f"gap0_{law}"] = gap(pl, sc, real, law, tl=tl)[0]
            except RuntimeError as e: print("skip", d, law, e)
        rows.append(row)
    return pd.DataFrame(rows)
def main(K=20, with_zero=False, tol=1.0):
    """tol: a gap counts as a reversal only if < -tol EUR (guards against 1e-9 numerical noise)."""
    X = scan(K, with_zero=with_zero); save(X, "E08_scan"); n = len(X)
    for law in LAWS:
        print(law, "reversals", int((X[f"gap_{law}"] < -tol).sum()), "/", n, "| mean aFRR %.0f | mean energy-side (gap - aFRR) %.0f | days with energy-side < 0: %d" %
              (X[f"aFRR_{law}"].mean(), X[f"energy_side_{law}"].mean(), int((X[f"energy_side_{law}"] < 0).sum())))
        if with_zero: print("   lambda_R=0 gap: max |gap0| = %.2e (identity P1==B2 when reserve revenue is zero)" % X[f"gap0_{law}"].abs().max())
if __name__ == "__main__": main()

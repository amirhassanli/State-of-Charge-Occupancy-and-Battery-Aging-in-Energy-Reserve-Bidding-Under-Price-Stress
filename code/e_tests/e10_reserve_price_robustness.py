"""E10 - replace the six fixed blog block means. (i) --auction_csv: user-supplied regelleistung.net aFRR capacity
results, columns: date (YYYY-MM-DD), block (1-6), pos_eur_mw_h, neg_eur_mw_h; the day's prices replace the fixed ones.
(ii) fallback: scale both price vectors by {0.5,0.75,1,1.25,1.5}. (The sandbox cannot reach regelleistung.net.)"""
import argparse, numpy as np, pandas as pd
from common import *
class prices:
    def __init__(s, up, dn): s.up, s.dn = np.asarray(up, float), np.asarray(dn, float)
    def __enter__(s): s.old = core.reserve_prices; core.reserve_prices = lambda: (s.up, s.dn)
    def __exit__(s, *a): core.reserve_prices = s.old
def main(day="2026-05-01", K=30, auction_csv=None, factors=(0.5, 0.75, 1, 1.25, 1.5)):
    _, _, _, sc, real = load(day, K); pl = plant(); up0, dn0 = core.reserve_prices(); rows = []
    if auction_csv:
        A = pd.read_csv(auction_csv); A = A[A.date == day].sort_values("block")
        assert len(A) == 6, "need six 4-h blocks for the day"
        with prices(np.repeat(A.pos_eur_mw_h, 4), np.repeat(A.neg_eur_mw_h, 4)):
            for law in LAWS: rows.append(dict(case="auction", law=law, gap=gap(pl, sc, real, law)[0]))
    for f in factors:
        with prices(up0*f, dn0*f):
            for law in LAWS: rows.append(dict(case=f"x{f}", law=law, gap=gap(pl, sc, real, law)[0]))
    X = pd.DataFrame(rows); save(X, "E10_reserve_prices"); print(X.pivot_table(index="case", columns="law", values="gap").round(1))
if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--auction_csv"); a = p.parse_args(); main(auction_csv=a.auction_csv)

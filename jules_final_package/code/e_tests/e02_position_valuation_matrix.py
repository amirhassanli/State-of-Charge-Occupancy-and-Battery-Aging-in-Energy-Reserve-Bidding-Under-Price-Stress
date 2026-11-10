"""E2 - 3x3 position-valuation matrix: bid optimised under law i, frozen, valued under law j.
If the off-diagonal values equal the diagonal, the difference is valuation; otherwise it is position."""
import pandas as pd
from common import *
def main(day="2026-05-01", K=30, exclusive=False):
    _, _, _, sc, real = load(day, K); pl = plant(); rows = []
    for li in LAWS:
        for flag, tag in ((False, "B2"), (True, "P1")):
            o = optimise(pl, sc, li, flag, exclusive=exclusive)
            win = float(o["bid"]["pda"][9:17].sum())
            for lj in LAWS:
                c = settle(pl, real, lj, o["bid"], exclusive=exclusive)
                rows.append(dict(bid_law=li, bid=tag, value_law=lj, pos_DA_09_16=win, **c))
    X = pd.DataFrame(rows); save(X, "E02_valuation_matrix")
    print(X.pivot_table(index=["bid","bid_law"], columns="value_law", values="Wholesale").round(1))
if __name__ == "__main__": main()

"""E6 - value function V(kappa-scale) and V(c_thr): sweep a multiplicative scale on the aging coefficients,
report B2 DA position in the trough window and objective value; a vertex switch shows as a jump of the position."""
import pandas as pd, numpy as np
from common import *
def main(day="2026-05-01", K=30, scales=(0, .25, .5, 1, 2, 4, 8, 10, 20, 50)):
    _, _, _, sc, real = load(day, K); rows = []
    for s in scales:
        for law in ("thr", "relcca_cal"):
            base = plant()
            if law == "thr": pl = plant(thr_cost=base.thr_cost*s)
            else: pl = plant(kappa_levels=tuple(np.array(base.kappa_levels)*s))
            o = optimise(pl, sc, law, False); b = o["bid"]["pda"]
            rows.append(dict(scale=s, law=law, value=o["value"], pos_09_16=float(b[9:17].sum()), pos_total=float(b.sum()),
                             aging_cost_proxy=float(settle(pl, real, law, dict(pda=b, rup=np.zeros(24), rdn=np.zeros(24)))["Aging"])))
    X = pd.DataFrame(rows).sort_values(["law", "scale"]); save(X, "E06_value_function")
    for law, g in X.groupby("law"):
        d = np.abs(np.diff(g.pos_09_16.values)); j = d.argmax()
        print(law, "largest position jump", round(d[j], 3), "MW-h between scale", g.scale.values[j], "and", g.scale.values[j+1])
if __name__ == "__main__": main()

"""E7 - separate a few-EUR difference from numerical noise: (i) LP re-solved at primal/dual tolerance 1e-7 and 1e-9
through scipy linprog(highs-ds); (ii) eps-optimal range of the trough-window DA position (core.eps_position_range)."""
import numpy as np, pandas as pd
from scipy.optimize import linprog
from common import *
def lp_value(spec, tol):
    A, lo, hi = spec["A"].tocsr(), spec["rlo"], spec["rhi"]; eq = np.isclose(lo, hi)
    import scipy.sparse as sp
    Aeq = A[eq]; beq = lo[eq]; ub_rows = []; bub = []
    mask_hi = (~eq) & np.isfinite(hi); mask_lo = (~eq) & np.isfinite(lo)
    Aub = sp.vstack([A[mask_hi], -A[mask_lo]]); bub = np.r_[hi[mask_hi], -lo[mask_lo]]
    r = linprog(-spec["obj"], A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=list(zip(spec["lb"], spec["ub"])),
                method="highs-ds", options=dict(primal_feasibility_tolerance=tol, dual_feasibility_tolerance=tol))
    return -r.fun, r.x
def main(day="2026-05-01", K=30, eps=(0.5, 4, 25, 100)):
    _, _, _, sc, real = load(day, K); pl = plant(); rows = []
    for law in LAWS:
        for flag, tag in ((False, "B2"), (True, "P1")):
            spec = build(pl, sc, law, flag); vals = {}
            for tol in (1e-7, 1e-9):
                v, x = lp_value(spec, tol); vals[tol] = v
                bid = dict(pda=x[spec["pda"]], rup=x[spec["rup"]], rdn=x[spec["rdn"]])
                vals[f"w_{tol}"] = settle(pl, real, law, bid)["Wholesale"]
            rows.append(dict(law=law, bid=tag, obj_1e7=vals[1e-7], obj_1e9=vals[1e-9], settled_1e7=vals["w_1e-07"], settled_1e9=vals["w_1e-09"]))
    X = pd.DataFrame(rows); save(X, "E07_tolerance")
    g = X.pivot_table(index="law", columns="bid", values=["settled_1e7", "settled_1e9"])
    print(g.round(2)); print("max |settled_1e7 - settled_1e9| =", float((X.settled_1e7 - X.settled_1e9).abs().max()))
    er = []
    for law in LAWS:
        o = optimise(pl, sc, law, False)
        for r in core.eps_position_range(o, range(9, 17), eps): er.append(dict(law=law, **r))
    E = pd.DataFrame(er); save(E, "E07_eps_range"); print(E.round(3))
if __name__ == "__main__": main()

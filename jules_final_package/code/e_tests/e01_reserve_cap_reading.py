"""E1 - reserve-cap reading. Reading (a): separate per-direction caps r_up<=R, r_dn<=R (repo default).
Reading (b): aggregate cap r_up+r_dn<=R at every hour. Reports max feasible aFRR revenue and P1-B2 gap."""
import numpy as np, pandas as pd, scipy.sparse as sp
from common import *
def aggregate_row(spec, R):
    """one constraint per hour: rup_t + rdn_t <= R, appended to spec; returns new spec."""
    s = dict(spec); n = spec["A"].shape[1]; rows = []
    for t in range(T):
        r = np.zeros(n); r[spec["rup"][t]] = 1; r[spec["rdn"][t]] = 1; rows.append(r)
    A = sp.vstack([spec["A"], sp.csr_matrix(np.array(rows))])
    s["A"] = A; s["rlo"] = np.r_[spec["rlo"], np.full(T, -np.inf)]; s["rhi"] = np.r_[spec["rhi"], np.full(T, R)]
    return s
def optimise_agg(pl, sc, law, reserve, agg):
    spec = build(pl, sc, law, reserve)
    if agg and reserve: spec = aggregate_row(spec, pl.rmax)
    r = run(spec, time_limit=120)
    return dict(spec=spec, res=r, bid=dict(pda=r.x[spec["pda"]], rup=r.x[spec["rup"]], rdn=r.x[spec["rdn"]]), value=-r.fun)
def main(day="2026-05-01", K=30):
    _, _, _, sc, real = load(day, K); pl = plant(); up, dn = core.reserve_prices()
    # per-direction ceiling: R*(sum up + sum dn); aggregate ceiling: best single direction every hour, R*sum(max(up,dn))
    print(f"ceiling aFRR EUR/day  per-direction: {pl.rmax*(up.sum()+dn.sum()):.1f}   aggregate (best direction each hour): {pl.rmax*np.maximum(up,dn).sum():.1f}   aggregate (one direction all day): {pl.rmax*max(up.sum(),dn.sum()):.1f}")
    rows = []
    for reading, agg in (("a_per_direction", False), ("b_aggregate", True)):
        for law in LAWS:
            res = {}
            for flag, tag in ((False, "B2"), (True, "P1")):
                o = optimise_agg(pl, sc, law, flag, agg)
                res[tag] = settle(pl, real, law, o["bid"])
            rows.append(dict(reading=reading, law=law, gap=res["P1"]["Wholesale"]-res["B2"]["Wholesale"],
                             aFRR_P1=res["P1"]["aFRR"], DA_B2=res["B2"]["DA"], DA_P1=res["P1"]["DA"]))
            print(rows[-1])
    save(pd.DataFrame(rows), "E01_reserve_cap_reading")
if __name__ == "__main__": main()

"""E5 - reserve-sustainment tau in {0.5,1,2,4}: gap per law, effective reserve (max/mean r_up, r_dn) and the
analytic energy-window ceiling r_up <= (Emax-Emin)*eta_d/tau ; tau* sign-change by linear interpolation."""
import pandas as pd, numpy as np
from common import *
def main(day="2026-05-01", K=30, taus=(0.5, 1, 2, 4)):
    _, _, _, sc, real = load(day, K); rows = []
    for tau in taus:
        pl = plant(tau=tau); ceil_up = (pl.Emax-pl.Emin)*pl.eta_d/tau; ceil_dn = (pl.Emax-pl.Emin)/(pl.eta_c*tau)
        for law in LAWS:
            g, o = gap(pl, sc, real, law)
            spec_bid = optimise(pl, sc, law, True)["bid"]
            rows.append(dict(tau=tau, law=law, gap=g, rup_max=spec_bid["rup"].max(), rup_mean=spec_bid["rup"].mean(),
                             rdn_max=spec_bid["rdn"].max(), rdn_mean=spec_bid["rdn"].mean(),
                             ceil_up=min(ceil_up, pl.rmax), ceil_dn=min(ceil_dn, pl.rmax),
                             window_binds=bool(ceil_up < pl.rmax or ceil_dn < pl.rmax), aFRR=o["P1"]["aFRR"]))
            print(rows[-1])
    X = pd.DataFrame(rows); save(X, "E05_tau_sweep")
    for law in LAWS:
        s = X[X.law == law].sort_values("tau"); sg = np.sign(s.gap.values)
        k = np.where(np.diff(sg) != 0)[0]
        if len(k): i = k[0]; t0, t1, g0, g1 = s.tau.values[i], s.tau.values[i+1], s.gap.values[i], s.gap.values[i+1]; print(law, "tau* ~", t0 - g0*(t1-t0)/(g1-g0))
        else: print(law, "no sign change on grid")
if __name__ == "__main__": main()

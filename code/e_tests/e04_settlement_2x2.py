"""E4 - {optimise under proxy | real reBAP} x {settle under proxy | real reBAP}.
CAVEAT (important): the optimise-under-real-reBAP cell feeds the *realised* reBAP into the scenarios, i.e. perfect
foresight of the imbalance price. It is labelled LEAKY. A leak-free cell needs a reBAP history (netztransparenz.de)
to build an ex-ante forecast: pass --rebap_hist CSV(date,hour,rebap) to enable cell 'exante'."""
import argparse, pandas as pd, numpy as np
from common import *
REBAP = os.path.join(REPO, "data/processed/real_rebap_afrr_2026-05-01.csv")
def with_prices(fn):
    class Ctx:
        def __enter__(s): s.old = core.imbalance_prices; core.imbalance_prices = fn
        def __exit__(s, *a): core.imbalance_prices = s.old
    return Ctx()
def single_price(vec):  # real reBAP is a single price: short pays it, long receives it
    return lambda lam, pl: (np.asarray(vec, float), np.asarray(vec, float))
def main(day="2026-05-01", K=30):
    reb = pd.read_csv(REBAP).sort_values("hour")["rebap_eur_mwh"].to_numpy()
    _, _, _, sc, real = load(day, K); pl = plant(); proxy = core.imbalance_prices; rows = []
    for opt_m in ("proxy", "reBAP_realised_LEAKY"):
        for set_m in ("proxy", "reBAP"):
            for law in LAWS:
                res = {}
                for flag, tag in ((False, "B2"), (True, "P1")):
                    with with_prices(single_price(reb) if opt_m != "proxy" else proxy):
                        o = optimise(pl, sc, law, flag)
                    with with_prices(single_price(reb) if set_m == "reBAP" else proxy):
                        res[tag] = settle(pl, real, law, o["bid"])
                rows.append(dict(optimise_under=opt_m, settle_under=set_m, law=law,
                                 gap=res["P1"]["Wholesale"] - res["B2"]["Wholesale"]))
    X = pd.DataFrame(rows); save(X, "E04_settlement_2x2")
    print(X.pivot_table(index=["optimise_under", "settle_under"], columns="law", values="gap").round(1))
if __name__ == "__main__": main()

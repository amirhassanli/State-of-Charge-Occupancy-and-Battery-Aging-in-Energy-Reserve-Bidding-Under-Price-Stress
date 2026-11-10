"""E12 - CVaR needs (1-alpha)K >= 1 scenarios in the tail: K=30 with alpha=0.95 gives 1.5. Report alpha/K grid and beta sweep.
beta sweep also prints the risk-penalty size so it can be compared with the aging effect."""
import numpy as np, pandas as pd
from common import *
def main(day="2026-05-01", Ks=(30, 100), alphas=(0.90, 0.95), betas=(0.0, 0.05, 0.2, 0.5)):
    rows = []
    for K in Ks:
        _, _, _, sc, real = load(day, K)
        for a in alphas:
            for b in betas:
                pl = plant(alpha=a, beta=b)
                for law in LAWS:
                    g, o = gap(pl, sc, real, law, beta=b); rows.append(dict(K=K, alpha=a, beta=b, tail_scen=(1-a)*K, law=law, gap=g))
    X = pd.DataFrame(rows); save(X, "E12_alpha_K_beta"); print(X.pivot_table(index=["K", "alpha", "beta"], columns="law", values="gap").round(1))
if __name__ == "__main__": main()

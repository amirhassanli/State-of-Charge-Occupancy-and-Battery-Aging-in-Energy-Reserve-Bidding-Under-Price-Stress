"""E11 - +-25% on the load scale (and optionally PV/wind) applied to scenarios and realised path alike."""
import numpy as np, pandas as pd
from common import *
def main(day="2026-05-01", K=30, factors=(0.75, 1.0, 1.25)):
    _, _, _, sc0, real0 = load(day, K); pl = plant(); rows = []
    for key in ("load", "pv", "wd"):
        for f in factors:
            sc = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in sc0.items()}; real = {k: v.copy() for k, v in real0.items()}
            sc[key] = sc[key]*f; real[key] = real[key]*f
            for law in LAWS: rows.append(dict(scaled=key, factor=f, law=law, gap=gap(pl, sc, real, law)[0]))
    X = pd.DataFrame(rows); save(X, "E11_scale"); print(X.pivot_table(index=["scaled", "factor"], columns="law", values="gap").round(1))
if __name__ == "__main__": main()

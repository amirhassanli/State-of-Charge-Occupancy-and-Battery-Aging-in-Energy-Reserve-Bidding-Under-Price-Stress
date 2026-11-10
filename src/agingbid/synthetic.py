"""Synthetic panel ONLY for code smoke tests.  Never report numbers from it."""
import numpy as np, pandas as pd
def make_panel(ndays=50, seed=1, path=None):
    rng = np.random.default_rng(seed); t = pd.date_range("2026-04-01", periods=24*ndays, freq="h", tz="Europe/Berlin")
    h = t.hour.values; d = np.repeat(np.arange(ndays), 24)
    sun = np.maximum(0, np.sin((h-6)/12*np.pi)); cl = np.clip(rng.normal(.7, .25, ndays), .1, 1)[d]
    pv = 4*sun*cl; wind = np.clip(1+0.6*np.repeat(np.cumsum(rng.normal(0, .3, ndays)), 24)*0+rng.normal(0, .5, len(t)), 0, 2)
    load = 4+0.8*np.sin((h-8)/24*2*np.pi)+rng.normal(0, .1, len(t))
    res = load-pv-wind; price = 70+25*res-15*(sun*cl)*6+rng.normal(0, 8, len(t))
    price[(d == ndays//2) & (h >= 10) & (h <= 15)] = -300
    df = pd.DataFrame(dict(timestamp=t.tz_convert("UTC").astype(str), da_price=price, load=load, pv=pv, wind=wind))
    if path: df.to_csv(path, index=False)
    return df

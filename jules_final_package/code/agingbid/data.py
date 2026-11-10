"""Panel -> daily matrices -> scenarios.  Leak-free: scenario errors only from days <= D-2."""
import numpy as np, pandas as pd

DEFAULT_COLS = dict(timestamp="timestamp", price="da_price", load="load", pv="pv", wind="wind",
                    load_fc=None, pv_fc=None, wind_fc=None)

def load_panel(path, cols=None):
    cols = {**DEFAULT_COLS, **(cols or {})}
    df = pd.read_csv(path)
    ts = pd.to_datetime(df[cols["timestamp"]], utc=True).dt.tz_convert("Europe/Berlin")
    df = df.assign(_ts=ts).sort_values("_ts").drop_duplicates("_ts")
    df["_date"] = df["_ts"].dt.date
    return df, cols

def daily_matrices(df, cols):
    names = ["price", "load", "pv", "wind"]
    cnt = df.groupby("_date").size(); days = [d for d in cnt.index if cnt[d] == 24]
    M = {}
    for nm in names:
        M[nm] = np.vstack([df.loc[df["_date"] == d, cols[nm]].to_numpy(float) for d in days])
    flat = lambda nm: M[nm].reshape(-1)
    def lag(a, h): out = np.full_like(a, np.nan); out[h:] = a[:-h]; return out
    # price forecast: leak-free (lags >=48h)
    M["price_fc"] = (0.5*(lag(flat("price"), 48)+lag(flat("price"), 168))).reshape(-1, 24)
    for nm in ("load", "pv", "wind"):
        c = cols.get(nm+"_fc")
        if c: M[nm+"_fc"] = np.vstack([df.loc[df["_date"] == d, c].to_numpy(float) for d in days])
        else: M[nm+"_fc"] = lag(flat(nm), 48).reshape(-1, 24)    # persistence fallback, D-2
    return days, M

def scenarios_for_day(M, i, K, rng, min_hist=14, pvcap=None, wdcap=None):
    """Draw K past-day error vectors (days <= i-2) and add them to day-i forecasts."""
    hist = [j for j in range(0, i-1) if not any(np.isnan(M[k][j]).any() for k in
            ("price", "price_fc", "load", "load_fc", "pv", "pv_fc", "wind", "wind_fc"))]
    if len(hist) < min_hist: return None
    pick = rng.choice(hist, K, replace=len(hist) < K)
    pvcap = pvcap or np.nanmax(M["pv"]); wdcap = wdcap or np.nanmax(M["wind"])
    e = {k: M[k][pick]-M[k+"_fc"][pick] for k in ("price", "load", "pv", "wind")}
    sc = dict(lam=M["price_fc"][i]+e["price"], load=np.maximum(M["load_fc"][i]+e["load"], 0),
              pv=np.clip(M["pv_fc"][i]+e["pv"], 0, pvcap), wd=np.clip(M["wind_fc"][i]+e["wind"], 0, wdcap),
              prob=np.full(K, 1.0/K))
    real = dict(lam=M["price"][i], load=M["load"][i], pv=M["pv"][i], wd=M["wind"][i])
    return sc, real

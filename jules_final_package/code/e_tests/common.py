"""Shared helpers for the E1-E12 identification tests.
Builds on the repository's own reconstruction (code/agingbid/core.py).
NOTHING here is the original (unavailable) model: every number produced is a
'reconstruction' number and must be labelled as such in the manuscript."""
import sys, os, json, copy
import numpy as np, pandas as pd
REPO = os.environ.get("AGINGBID_REPO", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.join(REPO, "code"))
from agingbid.core import Plant, build, run, optimise, settle, imbalance_prices, T
from agingbid.data import load_panel, daily_matrices, scenarios_for_day
import agingbid.core as core

LAWS = ["thr", "xu", "relcca"]
PANEL = os.environ.get("AGINGBID_PANEL", os.path.join(REPO, "data/processed/hourly_vpp_panel_2025-12-01_2026-08-21.csv"))
SEED = 20260821

def load(day="2026-05-01", K=30, seed=SEED):
    df, cols = load_panel(PANEL); days, M = daily_matrices(df, cols)
    i = [str(d) for d in days].index(day)
    sc, real = scenarios_for_day(M, i, K, np.random.default_rng(seed))
    return days, M, i, sc, real

def plant(**kw):
    pl = Plant(); [setattr(pl, k, v) for k, v in kw.items()]; return pl

def gap(pl, sc, real, law, exclusive=False, tl=120, beta=None, settle_pl=None):
    """P1-B2 wholesale gap: bid optimised on sc, frozen, settled on `real`."""
    out = {}
    for flag, tag in ((False, "B2"), (True, "P1")):
        o = optimise(pl, sc, law, flag, exclusive=exclusive, beta=beta, time_limit=tl)
        c = settle(settle_pl or pl, real, law, o["bid"], exclusive=exclusive)
        out[tag] = c
    return out["P1"]["Wholesale"] - out["B2"]["Wholesale"], out

def save(df, name, outdir="results"):
    os.makedirs(outdir, exist_ok=True); p = f"{outdir}/{name}.csv"; df.to_csv(p, index=False); print("saved", p); return p

#!/usr/bin/env python3
"""Gate 10 core: SMARD processing, scenario generation, HiGHS LP models B0/B2/P1."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linprog

ROOT = Path("/home/user")
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
TZ = "Europe/Berlin"

# ---------------------------------------------------------------------------
# VPP / market parameters (industrial-park aggregator, DE-LU)
# ---------------------------------------------------------------------------


@dataclass
class VPPParams:
    name: str = "DE industrial-park VPP (price-taker)"
    dt_h: float = 1.0
    T: int = 24
    # Ratings
    p_load_ref_mw: float = 5.0
    p_pv_rated_mw: float = 4.0
    p_wind_rated_mw: float = 2.0
    p_batt_mw: float = 2.5
    e_batt_mwh: float = 5.0
    eta_ch: float = 0.95
    eta_dis: float = 0.95
    soc_min_frac: float = 0.10
    soc_max_frac: float = 0.90
    soc_init_frac: float = 0.50
    p_dg_mw: float = 1.8
    c_dg_eur_mwh: float = 68.0
    dg_ramp_mw: float = 1.2
    c_deg_eur_mwh: float = 1.5
    r_max_mw: float = 1.5
    p_da_max_mw: float = 12.0
    # Risk (defaults; overridden per model)
    lam: float = 0.05
    alpha: float = 0.95
    K: int = 50
    seed: int = 20260821
    # Reserve capacity price shaping
    r_up_base: float = 9.0
    r_dn_base: float = 6.5
    # Imbalance two-price spreads (EUR/MWh)
    imb_short_add: float = 18.0
    imb_short_coef: float = 0.12
    imb_long_add: float = 10.0
    imb_long_coef: float = 0.08


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def _to_berlin(s):
    """Convert a timestamp Series or DatetimeIndex to Europe/Berlin."""
    if isinstance(s, pd.Series):
        ts = pd.to_datetime(s, utc=True)
        return ts.dt.tz_convert(TZ)
    idx = pd.DatetimeIndex(pd.to_datetime(s, utc=True))
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return idx.tz_convert(TZ)


def load_raw() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prices = pd.read_csv(RAW / "smard_da_prices_de_lu.csv", parse_dates=["timestamp"])
    power = pd.read_csv(RAW / "smard_public_power_de.csv", parse_dates=["timestamp"])
    fc = pd.read_csv(RAW / "smard_da_forecasts_de.csv", parse_dates=["timestamp"])
    prices["timestamp"] = _to_berlin(prices["timestamp"])
    power["timestamp"] = _to_berlin(power["timestamp"])
    fc["timestamp"] = _to_berlin(fc["timestamp"])
    return prices, power, fc


def build_hourly(params: VPPParams) -> pd.DataFrame:
    """Hourly aligned actuals + DA forecasts, scaled to VPP ratings."""
    prices, power, fc = load_raw()

    def hourly_mean(df, col, ts="timestamp"):
        s = df.set_index(ts)[col].astype(float)
        s.index = _to_berlin(s.index)
        return s.resample("h").mean()

    da = hourly_mean(prices, "da_price_eur_mwh")
    load_a = hourly_mean(power, "Load")
    solar_a = hourly_mean(power, "Solar")
    wind_on_a = hourly_mean(power, "Wind onshore")
    wind_off_a = hourly_mean(power, "Wind offshore")
    resid_a = hourly_mean(power, "Residual load")
    gas_a = hourly_mean(power, "Fossil gas")

    fc_w = fc.pivot_table(index="timestamp", columns="production_type", values="forecast_mw", aggfunc="mean")
    fc_w.index = _to_berlin(fc_w.index)
    fc_h = fc_w.resample("h").mean()

    df = pd.DataFrame(
        {
            "da_price": da,
            "load_nat": load_a,
            "solar_nat": solar_a,
            "wind_nat": wind_on_a + wind_off_a,
            "resid_nat": resid_a,
            "gas_nat": gas_a,
            "load_fc_nat": fc_h.get("load"),
            "solar_fc_nat": fc_h.get("solar"),
            "wind_fc_nat": fc_h.get("wind_onshore", 0) + fc_h.get("wind_offshore", 0),
        }
    )
    df = df.dropna(subset=["da_price", "load_nat", "solar_nat", "wind_nat"])
    df["wind_fc_nat"] = df["wind_fc_nat"].where(df["wind_fc_nat"].notna(), df["wind_nat"])
    df["solar_fc_nat"] = df["solar_fc_nat"].where(df["solar_fc_nat"].notna(), df["solar_nat"])
    df["load_fc_nat"] = df["load_fc_nat"].where(df["load_fc_nat"].notna(), df["load_nat"])

    # Scale national MW → VPP MW using study-window peaks (complete days only)
    complete = df.groupby(df.index.date).size()
    ok_days = complete[complete >= 24].index
    df["date"] = df.index.date
    study = df[df["date"].isin(ok_days)]
    load_ref = np.nanquantile(study["load_nat"].values, 0.95)
    solar_ref = np.nanmax(study["solar_nat"].values)
    wind_ref = np.nanmax(study["wind_nat"].values)
    sf_load = params.p_load_ref_mw / max(load_ref, 1.0)
    sf_pv = params.p_pv_rated_mw / max(solar_ref, 1.0)
    sf_w = params.p_wind_rated_mw / max(wind_ref, 1.0)

    df["load"] = df["load_nat"] * sf_load
    df["pv"] = df["solar_nat"] * sf_pv
    df["wind"] = df["wind_nat"] * sf_w
    df["load_fc"] = df["load_fc_nat"] * sf_load
    df["pv_fc"] = df["solar_fc_nat"] * sf_pv
    df["wind_fc"] = df["wind_fc_nat"] * sf_w
    df["hour"] = df.index.hour
    df["dow"] = df.index.dayofweek
    df["sf_load"] = sf_load
    df["sf_pv"] = sf_pv
    df["sf_w"] = sf_w

    # Persistence / similar-day DA price forecast (weekly + yesterday mix)
    df["da_price_y"] = df["da_price"].shift(24)
    df["da_price_w"] = df["da_price"].shift(24 * 7)
    df["da_price_fc"] = 0.55 * df["da_price_y"].fillna(df["da_price_w"]) + 0.45 * df["da_price_w"].fillna(df["da_price_y"])
    df["da_price_fc"] = df["da_price_fc"].fillna(df["da_price"].rolling(24, min_periods=1).mean())

    PROC.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out.index.name = "timestamp"
    out.to_csv(PROC / "hourly_vpp_smard.csv")
    meta = {
        "sf_load": float(sf_load),
        "sf_pv": float(sf_pv),
        "sf_w": float(sf_w),
        "load_ref_nat_mw": float(load_ref),
        "solar_ref_nat_mw": float(solar_ref),
        "wind_ref_nat_mw": float(wind_ref),
        "n_hours": int(len(df)),
        "start": str(df.index.min()),
        "end": str(df.index.max()),
        "source": "Bundesnetzagentur | SMARD.de via api.energy-charts.info (CC BY 4.0)",
    }
    (PROC / "scale_meta.json").write_text(json.dumps(meta, indent=2))
    return df


def complete_days(df: pd.DataFrame) -> List[pd.Timestamp]:
    g = df.groupby(df.index.date).size()
    days = [pd.Timestamp(d) for d, n in g.items() if n >= 24]
    return days


def slice_day(df: pd.DataFrame, day) -> pd.DataFrame:
    d = pd.Timestamp(day).tz_localize(None)
    # index is tz-aware Berlin
    mask = df.index.tz_localize(None).date == d.date() if df.index.tz is None else (df.index.date == pd.Timestamp(day).date())
    sub = df.loc[mask].iloc[:24]
    if len(sub) < 24:
        raise ValueError(f"Incomplete day {day}: {len(sub)} hours")
    return sub


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@dataclass
class ScenarioSet:
    day: str
    K: int
    T: int
    pi: np.ndarray
    # (K, T)
    price: np.ndarray
    load: np.ndarray
    pv: np.ndarray
    wind: np.ndarray
    imb_short: np.ndarray
    imb_long: np.ndarray
    r_up: np.ndarray  # (T,)
    r_dn: np.ndarray  # (T,)
    # point forecasts / actuals (T,)
    price_fc: np.ndarray
    load_fc: np.ndarray
    pv_fc: np.ndarray
    wind_fc: np.ndarray
    price_act: np.ndarray
    load_act: np.ndarray
    pv_act: np.ndarray
    wind_act: np.ndarray
    hist_errors: pd.DataFrame = field(repr=False, default=None)
    sampled_days: List[str] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)


def _imb_prices(da: np.ndarray, p: VPPParams) -> Tuple[np.ndarray, np.ndarray]:
    short = da + p.imb_short_add + p.imb_short_coef * np.abs(da)
    long = da - p.imb_long_add - p.imb_long_coef * np.abs(da)
    # two-price: long <= da <= short
    short = np.maximum(short, da + 5.0)
    long = np.minimum(long, da - 3.0)
    return short, long


def _reserve_prices(price_fc: np.ndarray, p: VPPParams) -> Tuple[np.ndarray, np.ndarray]:
    x = price_fc.copy()
    lo, hi = np.nanpercentile(x, 10), np.nanpercentile(x, 90)
    z = np.clip((x - lo) / max(hi - lo, 1.0), 0, 1)
    r_up = p.r_up_base + 7.0 * z
    r_dn = p.r_dn_base + 4.5 * z
    return r_up, r_dn


def historical_error_days(df: pd.DataFrame, op_day, lookback_days: int = 45) -> pd.DataFrame:
    """Daily 24-h error vectors for bootstrap (price, load, pv, wind)."""
    op = pd.Timestamp(op_day).date()
    days = complete_days(df)
    rows = []
    for d in days:
        dd = d.date() if hasattr(d, "date") else d
        if dd >= op:
            continue
        if (op - dd).days > lookback_days + 8:
            continue
        try:
            sub = slice_day(df, dd)
        except ValueError:
            continue
        if sub[["load_fc", "pv_fc", "wind_fc", "da_price_fc"]].isna().any().any():
            continue
        if len(sub) != 24:
            continue
        rec = {
            "date": str(dd),
            "e_price": (sub["da_price"] - sub["da_price_fc"]).values.astype(float),
            "e_load": (sub["load"] - sub["load_fc"]).values.astype(float),
            "e_pv": (sub["pv"] - sub["pv_fc"]).values.astype(float),
            "e_wind": (sub["wind"] - sub["wind_fc"]).values.astype(float),
        }
        rows.append(rec)
    if len(rows) < 8:
        raise RuntimeError(f"Too few historical error days before {op_day}: {len(rows)}")
    return pd.DataFrame(rows)


def build_scenarios(df: pd.DataFrame, op_day, params: VPPParams, K: Optional[int] = None) -> ScenarioSet:
    K = int(K or params.K)
    rng = np.random.default_rng(params.seed + int(pd.Timestamp(op_day).strftime("%Y%m%d")))
    day = slice_day(df, op_day)
    T = params.T
    hist = historical_error_days(df, op_day, lookback_days=50)
    n_h = len(hist)
    idx = rng.integers(0, n_h, size=K)
    sampled = [hist.iloc[i]["date"] for i in idx]

    price_fc = day["da_price_fc"].values.astype(float)
    load_fc = day["load_fc"].values.astype(float)
    pv_fc = day["pv_fc"].values.astype(float)
    wind_fc = day["wind_fc"].values.astype(float)

    price = np.zeros((K, T))
    load = np.zeros((K, T))
    pv = np.zeros((K, T))
    wind = np.zeros((K, T))
    for k, i in enumerate(idx):
        row = hist.iloc[int(i)]
        price[k] = price_fc + row["e_price"]
        load[k] = np.clip(load_fc + row["e_load"], 0.05, None)
        pv[k] = np.clip(pv_fc + row["e_pv"], 0.0, params.p_pv_rated_mw * 1.05)
        wind[k] = np.clip(wind_fc + row["e_wind"], 0.0, params.p_wind_rated_mw * 1.15)

    short, longp = _imb_prices(price, params)
    r_up, r_dn = _reserve_prices(price_fc, params)

    # diagnostics on errors
    E = np.vstack(hist["e_price"].to_list())
    El = np.vstack(hist["e_load"].to_list())
    Ep = np.vstack(hist["e_pv"].to_list())
    Ew = np.vstack(hist["e_wind"].to_list())
    diag = {
        "n_hist_days": int(n_h),
        "K": int(K),
        "op_day": str(pd.Timestamp(op_day).date()),
        "price_err_mae": float(np.mean(np.abs(E))),
        "price_err_rmse": float(np.sqrt(np.mean(E**2))),
        "load_err_mae": float(np.mean(np.abs(El))),
        "load_err_rmse": float(np.sqrt(np.mean(El**2))),
        "pv_err_mae": float(np.mean(np.abs(Ep))),
        "pv_err_rmse": float(np.sqrt(np.mean(Ep**2))),
        "wind_err_mae": float(np.mean(np.abs(Ew))),
        "wind_err_rmse": float(np.sqrt(np.mean(Ew**2))),
        "price_err_mean": float(np.mean(E)),
        "load_err_mean": float(np.mean(El)),
    }
    return ScenarioSet(
        day=str(pd.Timestamp(op_day).date()),
        K=K,
        T=T,
        pi=np.full(K, 1.0 / K),
        price=price,
        load=load,
        pv=pv,
        wind=wind,
        imb_short=short,
        imb_long=longp,
        r_up=r_up,
        r_dn=r_dn,
        price_fc=price_fc,
        load_fc=load_fc,
        pv_fc=pv_fc,
        wind_fc=wind_fc,
        price_act=day["da_price"].values.astype(float),
        load_act=day["load"].values.astype(float),
        pv_act=day["pv"].values.astype(float),
        wind_act=day["wind"].values.astype(float),
        hist_errors=hist,
        sampled_days=sampled,
        diagnostics=diag,
    )


def expected_scenario(scen: ScenarioSet, params: VPPParams) -> ScenarioSet:
    """Collapse to 1-scenario EV problem (B0)."""
    s = ScenarioSet(
        day=scen.day,
        K=1,
        T=scen.T,
        pi=np.array([1.0]),
        price=scen.price.mean(axis=0, keepdims=True),
        load=scen.load.mean(axis=0, keepdims=True),
        pv=scen.pv.mean(axis=0, keepdims=True),
        wind=scen.wind.mean(axis=0, keepdims=True),
        imb_short=scen.imb_short.mean(axis=0, keepdims=True),
        imb_long=scen.imb_long.mean(axis=0, keepdims=True),
        r_up=scen.r_up,
        r_dn=scen.r_dn,
        price_fc=scen.price_fc,
        load_fc=scen.load_fc,
        pv_fc=scen.pv_fc,
        wind_fc=scen.wind_fc,
        price_act=scen.price_act,
        load_act=scen.load_act,
        pv_act=scen.pv_act,
        wind_act=scen.wind_act,
        hist_errors=scen.hist_errors,
        sampled_days=["EV"],
        diagnostics=dict(scen.diagnostics),
    )
    s.diagnostics["K"] = 1
    s.diagnostics["mode"] = "expected_value"
    return s


def actual_as_scenario(scen: ScenarioSet, params: VPPParams) -> ScenarioSet:
    price = scen.price_act.reshape(1, -1)
    short, longp = _imb_prices(price, params)
    return ScenarioSet(
        day=scen.day,
        K=1,
        T=scen.T,
        pi=np.array([1.0]),
        price=price,
        load=scen.load_act.reshape(1, -1),
        pv=scen.pv_act.reshape(1, -1),
        wind=scen.wind_act.reshape(1, -1),
        imb_short=short,
        imb_long=longp,
        r_up=scen.r_up,
        r_dn=scen.r_dn,
        price_fc=scen.price_fc,
        load_fc=scen.load_fc,
        pv_fc=scen.pv_fc,
        wind_fc=scen.wind_fc,
        price_act=scen.price_act,
        load_act=scen.load_act,
        pv_act=scen.pv_act,
        wind_act=scen.wind_act,
        hist_errors=scen.hist_errors,
        sampled_days=["ACTUAL"],
        diagnostics={"mode": "realized"},
    )


# ---------------------------------------------------------------------------
# LP builder (HiGHS via scipy.optimize.linprog)
# ---------------------------------------------------------------------------


class _LP:
    def __init__(self, n: int):
        self.n = n
        self.c = np.zeros(n)
        self.eq_r, self.eq_c, self.eq_v, self.eq_b = [], [], [], []
        self.ub_r, self.ub_c, self.ub_v, self.ub_b = [], [], [], []
        self.lo = np.full(n, -np.inf)
        self.hi = np.full(n, np.inf)

    def obj(self, j, v):
        self.c[j] += v

    def bnd(self, j, lo, hi):
        self.lo[j] = lo
        self.hi[j] = hi

    def eq(self, terms: List[Tuple[int, float]], b: float):
        i = len(self.eq_b)
        for j, v in terms:
            if v != 0.0:
                self.eq_r.append(i)
                self.eq_c.append(j)
                self.eq_v.append(v)
        self.eq_b.append(b)

    def le(self, terms: List[Tuple[int, float]], b: float):
        i = len(self.ub_b)
        for j, v in terms:
            if v != 0.0:
                self.ub_r.append(i)
                self.ub_c.append(j)
                self.ub_v.append(v)
        self.ub_b.append(b)

    def solve(self):
        A_eq = sparse.coo_matrix(
            (self.eq_v, (self.eq_r, self.eq_c)), shape=(len(self.eq_b), self.n)
        ).tocsr() if self.eq_b else None
        b_eq = np.array(self.eq_b) if self.eq_b else None
        A_ub = sparse.coo_matrix(
            (self.ub_v, (self.ub_r, self.ub_c)), shape=(len(self.ub_b), self.n)
        ).tocsr() if self.ub_b else None
        b_ub = np.array(self.ub_b) if self.ub_b else None
        bounds = list(zip(self.lo.tolist(), self.hi.tolist()))
        t0 = time.perf_counter()
        res = linprog(
            self.c,
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
            options={"disp": False, "time_limit": 60.0, "presolve": True},
        )
        runtime = time.perf_counter() - t0
        return res, runtime


def _profit_terms(s, t, ix, scen, params, use_reserve: bool):
    """Linear coefficients of profit_s (EUR) for scenario s hour t (summed later)."""
    terms = []
    terms.append((ix["pda"] + t, float(scen.price[s, t])))
    if use_reserve:
        terms.append((ix["rup"] + t, float(scen.r_up[t])))
        terms.append((ix["rdn"] + t, float(scen.r_dn[t])))
    terms.append((ix["ilong"][s] + t, float(scen.imb_long[s, t])))
    terms.append((ix["ishort"][s] + t, -float(scen.imb_short[s, t])))
    terms.append((ix["pdg"][s] + t, -float(params.c_dg_eur_mwh)))
    terms.append((ix["pch"][s] + t, -float(params.c_deg_eur_mwh)))
    terms.append((ix["pdis"][s] + t, -float(params.c_deg_eur_mwh)))
    return terms


def build_and_solve(
    scen: ScenarioSet,
    params: VPPParams,
    model: str,
    lam: Optional[float] = None,
    alpha: Optional[float] = None,
    use_reserve: Optional[bool] = None,
    fix_first_stage: Optional[dict] = None,
) -> dict:
    """
    Models
    ------
    B0 : expected-value, λ=0, no reserve (caller should pass K=1 EV scen)
    B2 : two-stage mean–CVaR, energy only
    P1 : two-stage mean–CVaR, joint energy–reserve (proposed)
    """
    model = model.upper()
    T, K = scen.T, scen.K
    lam = params.lam if lam is None else float(lam)
    alpha = params.alpha if alpha is None else float(alpha)
    if use_reserve is None:
        use_reserve = model == "P1"
    if model == "B0":
        lam = 0.0
        use_reserve = False

    dt = params.dt_h
    soc_min = params.soc_min_frac * params.e_batt_mwh
    soc_max = params.soc_max_frac * params.e_batt_mwh
    soc_init = params.soc_init_frac * params.e_batt_mwh
    eta_c, eta_d = params.eta_ch, params.eta_dis

    # variable layout
    ix = {}
    n = 0
    ix["pda"] = n
    n += T
    ix["rup"] = n
    n += T
    ix["rdn"] = n
    n += T
    ix["pch"] = [0] * K
    ix["pdis"] = [0] * K
    ix["soc"] = [0] * K
    ix["pdg"] = [0] * K
    ix["ishort"] = [0] * K
    ix["ilong"] = [0] * K
    for s in range(K):
        ix["pch"][s] = n
        n += T
        ix["pdis"][s] = n
        n += T
        ix["soc"][s] = n
        n += T
        ix["pdg"][s] = n
        n += T
        ix["ishort"][s] = n
        n += T
        ix["ilong"][s] = n
        n += T
    use_cvar = lam > 1e-12
    if use_cvar:
        ix["eta"] = n
        n += 1
        ix["z"] = n
        n += K

    lp = _LP(n)

    # bounds
    for t in range(T):
        lp.bnd(ix["pda"] + t, -params.p_da_max_mw, params.p_da_max_mw)
        if use_reserve:
            lp.bnd(ix["rup"] + t, 0.0, params.r_max_mw)
            lp.bnd(ix["rdn"] + t, 0.0, params.r_max_mw)
        else:
            lp.bnd(ix["rup"] + t, 0.0, 0.0)
            lp.bnd(ix["rdn"] + t, 0.0, 0.0)
    for s in range(K):
        for t in range(T):
            lp.bnd(ix["pch"][s] + t, 0.0, params.p_batt_mw)
            lp.bnd(ix["pdis"][s] + t, 0.0, params.p_batt_mw)
            lp.bnd(ix["soc"][s] + t, soc_min, soc_max)
            lp.bnd(ix["pdg"][s] + t, 0.0, params.p_dg_mw)
            lp.bnd(ix["ishort"][s] + t, 0.0, 20.0)
            lp.bnd(ix["ilong"][s] + t, 0.0, 20.0)
    if use_cvar:
        lp.bnd(ix["eta"], -1e7, 1e7)
        for s in range(K):
            lp.bnd(ix["z"] + s, 0.0, 1e7)

    if fix_first_stage is not None:
        pda = np.asarray(fix_first_stage["pda"], dtype=float)
        rup = np.asarray(fix_first_stage.get("rup", np.zeros(T)), dtype=float)
        rdn = np.asarray(fix_first_stage.get("rdn", np.zeros(T)), dtype=float)
        for t in range(T):
            lp.bnd(ix["pda"] + t, pda[t], pda[t])
            if use_reserve:
                lp.bnd(ix["rup"] + t, rup[t], rup[t])
                lp.bnd(ix["rdn"] + t, rdn[t], rdn[t])
            else:
                lp.bnd(ix["rup"] + t, 0.0, 0.0)
                lp.bnd(ix["rdn"] + t, 0.0, 0.0)

    # equalities: power balance, SoC dynamics, cyclic SoC
    for s in range(K):
        for t in range(T):
            # p_da + p_ch + load + imb_long = pv + wind + p_dg + p_dis + imb_short
            lp.eq(
                [
                    (ix["pda"] + t, 1.0),
                    (ix["pch"][s] + t, 1.0),
                    (ix["ilong"][s] + t, 1.0),
                    (ix["pdis"][s] + t, -1.0),
                    (ix["pdg"][s] + t, -1.0),
                    (ix["ishort"][s] + t, -1.0),
                ],
                float(scen.pv[s, t] + scen.wind[s, t] - scen.load[s, t]),
            )
            # SoC_t = SoC_{t-1} + eta_c dt p_ch - dt p_dis / eta_d
            if t == 0:
                lp.eq(
                    [
                        (ix["soc"][s] + t, 1.0),
                        (ix["pch"][s] + t, -eta_c * dt),
                        (ix["pdis"][s] + t, dt / eta_d),
                    ],
                    soc_init,
                )
            else:
                lp.eq(
                    [
                        (ix["soc"][s] + t, 1.0),
                        (ix["soc"][s] + t - 1, -1.0),
                        (ix["pch"][s] + t, -eta_c * dt),
                        (ix["pdis"][s] + t, dt / eta_d),
                    ],
                    0.0,
                )
        # cyclic: soc_T == soc_init
        lp.eq([(ix["soc"][s] + (T - 1), 1.0)], soc_init)

    # inequalities: DG ramp, reserve headroom, CVaR
    for s in range(K):
        for t in range(1, T):
            lp.le([(ix["pdg"][s] + t, 1.0), (ix["pdg"][s] + t - 1, -1.0)], params.dg_ramp_mw)
            lp.le([(ix["pdg"][s] + t, -1.0), (ix["pdg"][s] + t - 1, 1.0)], params.dg_ramp_mw)
        if use_reserve:
            for t in range(T):
                # discharge + DG headroom + r_up <= batt + dg
                lp.le(
                    [
                        (ix["pdis"][s] + t, 1.0),
                        (ix["pdg"][s] + t, 1.0),
                        (ix["rup"] + t, 1.0),
                    ],
                    params.p_batt_mw + params.p_dg_mw,
                )
                # charge + r_dn <= batt
                lp.le([(ix["pch"][s] + t, 1.0), (ix["rdn"] + t, 1.0)], params.p_batt_mw)
                # energy for upward reserve: soc - r_up*dt/eta_d >= soc_min
                lp.le(
                    [(ix["rup"] + t, dt / eta_d), (ix["soc"][s] + t, -1.0)],
                    -soc_min,
                )
                # energy for downward reserve: soc + r_dn*dt*eta_c <= soc_max
                lp.le(
                    [(ix["soc"][s] + t, 1.0), (ix["rdn"] + t, eta_c * dt)],
                    soc_max,
                )

    pi = scen.pi
    # objective: minimize  -(1-λ) E[profit]  - λ CVaR
    # CVaR = eta - 1/(1-α) E[z],  z_s >= eta - profit_s
    w = (1.0 - lam) * pi  # weight on E[profit] in the MAX sense
    for s in range(K):
        for t in range(T):
            for j, v in _profit_terms(s, t, ix, scen, params, use_reserve):
                lp.obj(j, -w[s] * v)  # min -w*profit
        if use_cvar:
            # z_s >= eta - profit_s  =>  -profit_s + eta - z_s <= 0
            terms = [(ix["eta"], 1.0), (ix["z"] + s, -1.0)]
            for t in range(T):
                for j, v in _profit_terms(s, t, ix, scen, params, use_reserve):
                    terms.append((j, -v))
            lp.le(terms, 0.0)
    if use_cvar:
        lp.obj(ix["eta"], -lam)
        inv = lam / max(1.0 - alpha, 1e-9)
        for s in range(K):
            lp.obj(ix["z"] + s, inv * pi[s])

    res, runtime = lp.solve()
    status = "HighsModelStatus.kOptimal" if res.success else f"HighsModelStatus.FAIL:{res.status}:{res.message}"
    x = res.x if res.x is not None else np.zeros(n)

    def take(start, length):
        return x[start : start + length].copy()

    pda = take(ix["pda"], T)
    rup = take(ix["rup"], T)
    rdn = take(ix["rdn"], T)
    pch = np.vstack([take(ix["pch"][s], T) for s in range(K)])
    pdis = np.vstack([take(ix["pdis"][s], T) for s in range(K)])
    soc = np.vstack([take(ix["soc"][s], T) for s in range(K)])
    pdg = np.vstack([take(ix["pdg"][s], T) for s in range(K)])
    ishort = np.vstack([take(ix["ishort"][s], T) for s in range(K)])
    ilong = np.vstack([take(ix["ilong"][s], T) for s in range(K)])

    profit_st = np.zeros((K, T))
    for s in range(K):
        profit_st[s] = (
            scen.price[s] * pda
            + (scen.r_up * rup + scen.r_dn * rdn if use_reserve else 0.0)
            + scen.imb_long[s] * ilong[s]
            - scen.imb_short[s] * ishort[s]
            - params.c_dg_eur_mwh * pdg[s]
            - params.c_deg_eur_mwh * (pch[s] + pdis[s])
        )
    profit_s = profit_st.sum(axis=1)
    e_profit = float(profit_s @ pi)
    if use_cvar:
        eta = float(x[ix["eta"]])
        z = take(ix["z"], K)
        cvar = float(eta - (1.0 / max(1.0 - alpha, 1e-9)) * (z @ pi))
    else:
        eta = float(np.quantile(profit_s, 1.0 - max(alpha, 0.5))) if K > 1 else e_profit
        z = np.zeros(K)
        # empirical CVaR of the (single or EV) profit
        if K == 1:
            cvar = e_profit
        else:
            q = np.quantile(profit_s, 1.0 - alpha)
            tail = profit_s[profit_s <= q]
            cvar = float(tail.mean()) if len(tail) else e_profit

    obj_reported = float((1.0 - lam) * e_profit + lam * cvar)

    return {
        "model": model,
        "status": status,
        "success": bool(res.success),
        "message": str(res.message),
        "runtime_s": float(runtime),
        "n_vars": int(n),
        "n_eq": int(len(lp.eq_b)),
        "n_ineq": int(len(lp.ub_b)),
        "lam": float(lam),
        "alpha": float(alpha),
        "K": int(K),
        "use_reserve": bool(use_reserve),
        "day": scen.day,
        "pda": pda,
        "rup": rup,
        "rdn": rdn,
        "pch": pch,
        "pdis": pdis,
        "soc": soc,
        "pdg": pdg,
        "ishort": ishort,
        "ilong": ilong,
        "profit_st": profit_st,
        "profit_s": profit_s,
        "e_profit": e_profit,
        "cvar": float(cvar),
        "eta": float(eta),
        "obj": obj_reported,
        "pi": pi.copy(),
        "solver_fun": float(res.fun) if res.fun is not None else np.nan,
        "highs_nit": int(getattr(res, "nit", 0) or 0),
    }


def empirical_cvar(x: np.ndarray, alpha: float) -> float:
    x = np.asarray(x, dtype=float)
    q = np.quantile(x, 1.0 - alpha)
    tail = x[x <= q + 1e-9]
    return float(tail.mean()) if len(tail) else float(x.mean())


def evaluate_first_stage(
    sol: dict,
    scen: ScenarioSet,
    params: VPPParams,
    use_reserve: Optional[bool] = None,
) -> dict:
    """Fix first-stage decisions and re-optimize recourse on given scenarios (in-sample or OOS)."""
    if use_reserve is None:
        use_reserve = bool(sol.get("use_reserve", sol["model"] == "P1"))
    fix = {"pda": sol["pda"], "rup": sol["rup"] if use_reserve else np.zeros(scen.T), "rdn": sol["rdn"] if use_reserve else np.zeros(scen.T)}
    rec = build_and_solve(
        scen,
        params,
        model=sol["model"],
        lam=0.0,  # pure expected recourse profit
        alpha=sol["alpha"],
        use_reserve=use_reserve,
        fix_first_stage=fix,
    )
    rec["parent_model"] = sol["model"]
    rec["evaluation"] = "recourse"
    rec["cvar_emp"] = empirical_cvar(rec["profit_s"], sol["alpha"])
    return rec


def numpy_to_list(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, dict):
        return {k: numpy_to_list(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [numpy_to_list(v) for v in obj]
    return obj

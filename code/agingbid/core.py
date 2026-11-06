"""Common daily mean-CVaR energy-reserve LP/MILP with three exchangeable aging laws.

Re-implementation written from the equations of the manuscript (the original
src/relcca_model.py was not available).  PLACEHOLDERS that the manuscript does not
state are flagged `# ASSUMPTION` and MUST be replaced by the values actually used
in the published runs before any number from this code is quoted.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import scipy.sparse as sp
from scipy.optimize import milp, LinearConstraint, Bounds

T = 24
POS_BLOCKS = (4.5, 12.0, 47.1, 18.4, 35.6, 8.0)   # EUR/MW/h, manuscript Sec. III-C
NEG_BLOCKS = (6.0, 15.0, 36.9, 57.4, 20.0, 2.4)


@dataclass
class Plant:
    PB: float = 2.5; Eb: float = 5.0
    eta_c: float = 0.95; eta_d: float = 0.95
    soc_min: float = 0.10; soc_max: float = 0.90
    gmax: float = 1.8; gcost: float = 68.0; ramp: float = 1.2
    rmax: float = 1.5
    tau: float = 1.0            # ASSUMPTION: reserve sustainment hours (value not stated in manuscript)
    thr_cost: float = 1.5
    beta: float = 0.05; alpha: float = 0.95
    N: int = 8
    kappa_levels: tuple = (0.247, 0.493, 0.822)
    kappa_map: tuple = (0, 0, 1, 1, 1, 2, 2, 2)
    gamma_charge_base: float = 1.5  # ASSUMPTION: manuscript gives no gamma values
    gamma_discharge_base: float = 1.5  # ASSUMPTION
    gamma_charge_scale: tuple = (0.8, 0.8, 1, 1, 1, 1.2, 1.2, 1.2)  # ASSUMPTION
    gamma_discharge_scale: tuple = (0.8, 0.8, 1, 1, 1, 1.2, 1.2, 1.2)  # ASSUMPTION
    xu_w: tuple = (0.2, 0.3, 0.3, 0.2); xu_m: tuple = (10, 40, 80, 120)
    imb_short=(18.0, 0.12, 5.0); imb_long=(10.0, 0.08, 3.0)   # proxy, NOT reBAP
    @property
    def Emin(self): return self.soc_min*self.Eb
    @property
    def Emax(self): return self.soc_max*self.Eb
    @property
    def E0(self): return 0.5*(self.Emin+self.Emax)   # ASSUMPTION: cyclic start level


def reserve_prices():
    up = np.repeat(POS_BLOCKS, 4); dn = np.repeat(NEG_BLOCKS, 4)
    return up.astype(float), dn.astype(float)


def imbalance_prices(lam, pl: Plant):
    a, b, m = pl.imb_short; short = np.maximum(lam + a + b*np.abs(lam), lam + m)
    a, b, m = pl.imb_long;  long_ = np.minimum(lam - a - b*np.abs(lam), lam - m)
    return short, long_


class _B:
    def __init__(s):
        s.n = 0; s.lb = []; s.ub = []; s.integ = []
        s.r = []; s.c = []; s.v = []; s.rlo = []; s.rhi = []; s.nr = 0
    def var(s, n, lb=0.0, ub=np.inf, integer=False):
        idx = np.arange(s.n, s.n+n); s.n += n
        s.lb += list(np.broadcast_to(lb, (n,))); s.ub += list(np.broadcast_to(ub, (n,)))
        s.integ += [1 if integer else 0]*n
        return idx
    def con(s, idx, coef, lo=-np.inf, hi=np.inf):
        idx = np.atleast_1d(idx); coef = np.broadcast_to(np.atleast_1d(coef), idx.shape)
        s.r += [s.nr]*len(idx); s.c += list(idx); s.v += list(coef)
        s.rlo.append(lo); s.rhi.append(hi); s.nr += 1


def build(pl: Plant, sc: dict, law: str, reserve: bool, exclusive: bool = False,
          fixed: dict | None = None, beta: float | None = None):
    """sc: arrays (K,T): lam, pv, wd, load; prob (K,).  law in {thr, xu, relcca, relcca_cal, relcca_cyc}."""
    K = sc["lam"].shape[0]; prob = np.asarray(sc["prob"], float)
    beta = pl.beta if beta is None else beta
    up, dn = reserve_prices()
    b = _B()
    big = 50.0
    pda = b.var(T, -big, big)
    rub = pl.rmax if reserve else 0.0
    rup = b.var(T, 0, rub); rdn = b.var(T, 0, rub)
    if fixed is not None:
        for nm, ix in (("pda", pda), ("rup", rup), ("rdn", rdn)):
            for k, i in enumerate(ix): b.lb[i] = b.ub[i] = float(fixed[nm][k])
    P = b.var(K, -np.inf, np.inf)
    zeta = b.var(1, -np.inf, np.inf)[0]; s_ = b.var(K, 0, np.inf)
    obj = np.zeros(0); terms = []   # (idx, coef) for maximisation
    sol = []
    for w in range(K):
        lam = sc["lam"][w]; ish_p, ilg_p = imbalance_prices(lam, pl)
        ch = b.var(T, 0, pl.PB); dis = b.var(T, 0, pl.PB)
        E = b.var(T, pl.Emin, pl.Emax); g = b.var(T, 0, pl.gmax)
        pvu = b.var(T, 0, np.maximum(sc["pv"][w], 0)); wu = b.var(T, 0, np.maximum(sc["wd"][w], 0))
        ish = b.var(T); ilg = b.var(T)
        age = []   # list of (idx, coef) minimisation-cost terms
        for t in range(T):
            b.con([pvu[t], wu[t], g[t], dis[t], ish[t], ch[t], ilg[t], pda[t]],
                  [1, 1, 1, 1, 1, -1, -1, -1], sc["load"][w][t], sc["load"][w][t])
            prevE = [] if t == 0 else [E[t-1]]
            b.con([E[t]]+prevE+[ch[t], dis[t]], [1]+([-1] if t else [])+[-pl.eta_c, 1/pl.eta_d],
                  pl.E0 if t == 0 else 0.0, pl.E0 if t == 0 else 0.0)
            if t:
                b.con([g[t], g[t-1]], [1, -1], -pl.ramp, pl.ramp)
            b.con([rup[t], dis[t]], [1, 1], -np.inf, pl.PB)
            b.con([E[t], rup[t]], [-1, pl.tau/pl.eta_d], -np.inf, -pl.Emin)
            b.con([rdn[t], ch[t]], [1, 1], -np.inf, pl.PB)
            b.con([E[t], rdn[t]], [1, pl.eta_c*pl.tau], -np.inf, pl.Emax)
        b.con([E[T-1]], [1], pl.E0, pl.E0)
        ymap = None
        if exclusive:
            y = b.var(T, 0, 1, integer=True)
            for t in range(T):
                b.con([ch[t], y[t]], [1, -pl.PB], -np.inf, 0.0)
                b.con([dis[t], y[t]], [1, pl.PB], -np.inf, pl.PB)
        # ---- aging laws
        if law == "thr":
            age += [(ch, pl.thr_cost), (dis, pl.thr_cost)]
        elif law == "xu":
            Emx = b.var(1, pl.Emin, pl.Emax)[0]; Emn = b.var(1, pl.Emin, pl.Emax)[0]
            dl = b.var(4, 0, np.array(pl.xu_w))
            for t in range(T):
                b.con([E[t], Emx], [1, -1], -np.inf, 0); b.con([E[t], Emn], [1, -1], 0, np.inf)
            b.con(list(dl)+[Emx, Emn], [1]*4+[-1/pl.Eb, 1/pl.Eb], 0, np.inf)
            age += [(dl, np.array(pl.xu_m, float))]
        elif law.startswith("relcca"):
            N = pl.N; dE = (pl.Emax-pl.Emin)/N
            kap = np.array([pl.kappa_levels[i] for i in pl.kappa_map]) if N == 8 else \
                  np.array(pl.kappa_levels)[np.minimum((np.arange(N)*3)//N, 2)]
            gam_ch = pl.gamma_charge_base*(np.array(pl.gamma_charge_scale) if N == 8 else np.ones(N))
            gam_dis = pl.gamma_discharge_base*(np.array(pl.gamma_discharge_scale) if N == 8 else np.ones(N))
            use_cal = law in ("relcca", "relcca_cal"); use_cyc = law in ("relcca", "relcca_cyc")
            u = [b.var(T, 0, 1) for _ in range(N)]
            cb = [b.var(T, 0) for _ in range(N)]; db = [b.var(T, 0) for _ in range(N)]
            u_init = np.clip((pl.E0-pl.Emin-np.arange(N)*dE)/dE, 0, 1)
            for t in range(T):
                for l in range(1, N): b.con([u[l][t], u[l-1][t]], [1, -1], -np.inf, 0)
                b.con([E[t]]+[u[l][t] for l in range(N)], [1]+[-dE]*N, pl.Emin, pl.Emin)
                b.con([ch[t]]+[cb[l][t] for l in range(N)], [1]+[-1]*N, 0, 0)
                b.con([dis[t]]+[db[l][t] for l in range(N)], [1]+[-1]*N, 0, 0)
                for l in range(N):
                    pv_ = ([u[l][t-1]] if t else [])
                    b.con([u[l][t]]+pv_+[cb[l][t], db[l][t]],
                          [dE]+([-dE] if t else [])+[-pl.eta_c, 1/pl.eta_d],
                          0.0 if t else dE*u_init[l], 0.0 if t else dE*u_init[l])
            for l in range(N):
                if use_cal: age.append((u[l], kap[l]*dE))
                if use_cyc: age += [(cb[l], gam_ch[l]), (db[l], gam_dis[l])]
        else:
            raise ValueError(law)
        # ---- scenario profit definition
        idx = [P[w]]; co = [1.0]
        idx += list(pda); co += list(-lam)
        idx += list(rup); co += list(-up); idx += list(rdn); co += list(-dn)
        idx += list(ilg); co += list(-ilg_p); idx += list(ish); co += list(ish_p)
        idx += list(g); co += [pl.gcost]*T
        for ix, cf in age:
            ix = np.atleast_1d(ix); idx += list(ix); co += list(np.broadcast_to(cf, ix.shape))
        b.con(idx, co, 0, 0)
        b.con([P[w], zeta, s_[w]], [-1, -1, -1], -np.inf, 0)
        sol.append(dict(ch=ch, dis=dis, E=E, g=g, ish=ish, ilg=ilg, age=age, lam=lam, ish_p=ish_p, ilg_p=ilg_p))
    c = np.zeros(b.n)
    c[P] += prob
    if beta > 0:
        c[zeta] -= beta; c[s_] -= beta*prob/(1-pl.alpha)
    A = sp.csr_matrix((b.v, (b.r, b.c)), shape=(b.nr, b.n))
    return dict(A=A, rlo=np.array(b.rlo), rhi=np.array(b.rhi), lb=np.array(b.lb), ub=np.array(b.ub),
                integ=np.array(b.integ), obj=c, pda=pda, rup=rup, rdn=rdn, P=P, K=K, sol=sol, pl=pl,
                prob=prob, up=up, dn=dn)


def solve(spec, time_limit=120, gap=1e-6, extra_row=None):
    A, rlo, rhi = spec["A"], spec["rlo"], spec["rhi"]
    if extra_row is not None:
        row, lo, hi = extra_row
        A = sp.vstack([A, sp.csr_matrix(row.reshape(1, -1))]); rlo = np.r_[rlo, lo]; rhi = np.r_[rhi, hi]
    return A, rlo, rhi


def run(spec, c=None, time_limit=120, gap=1e-6, extra_row=None):
    A, rlo, rhi = solve(spec, extra_row=extra_row)
    c = -spec["obj"] if c is None else c
    r = milp(c=c, constraints=LinearConstraint(A, rlo, rhi), integrality=spec["integ"],
             bounds=Bounds(spec["lb"], spec["ub"]), options=dict(time_limit=time_limit, mip_rel_gap=gap))
    return r


def optimise(pl, sc, law, reserve, exclusive=False, beta=None, time_limit=120):
    spec = build(pl, sc, law, reserve, exclusive, beta=beta)
    r = run(spec, time_limit=time_limit)
    if r.x is None: raise RuntimeError(f"solver failed: {r.message}")
    bid = dict(pda=r.x[spec["pda"]], rup=r.x[spec["rup"]], rdn=r.x[spec["rdn"]])
    return dict(spec=spec, res=r, bid=bid, value=-r.fun, ok=(r.status == 0))


def settle(pl, realized, law, bid, exclusive=False):
    """Freeze first stage, re-optimise recourse on the realised path under `law`."""
    sc = {k: np.asarray(v)[None, :] for k, v in realized.items()}; sc["prob"] = np.ones(1)
    spec = build(pl, sc, law, reserve=True, exclusive=exclusive, fixed=bid, beta=0.0)
    r = run(spec)
    if r.x is None: raise RuntimeError(f"settlement failed: {r.message}")
    x = r.x; s0 = spec["sol"][0]; lam = s0["lam"]
    comp = dict(
        DA=float(lam @ x[spec["pda"]]),
        aFRR=float(spec["up"] @ x[spec["rup"]] + spec["dn"] @ x[spec["rdn"]]),
        Imb=float(s0["ilg_p"] @ x[s0["ilg"]] - s0["ish_p"] @ x[s0["ish"]]),
        DG=float(-pl.gcost*x[s0["g"]].sum()),
        Aging=float(-sum((np.broadcast_to(cf, np.atleast_1d(ix).shape)*x[np.atleast_1d(ix)]).sum() for ix, cf in s0["age"])))
    comp["Wholesale"] = comp["DA"]+comp["aFRR"]+comp["Imb"]+comp["DG"]+comp["Aging"]
    comp["overlap_MWh"] = float(np.minimum(x[s0["ch"]], x[s0["dis"]]).sum())
    return comp


def overlap_in_solution(opt):
    """Simultaneous charge/discharge diagnostic for an optimised first-stage solve."""
    x = opt["res"].x; out = []
    for s in opt["spec"]["sol"]:
        out.append(float(np.minimum(x[s["ch"]], x[s["dis"]]).sum()))
    return dict(mean=float(np.mean(out)), max=float(np.max(out)),
                share_scen_with_overlap=float(np.mean(np.array(out) > 1e-6)))


def eps_position_range(opt, window, eps_list):
    """Range of sum(pda[window]) over the eps-optimal set -> near-tie / degeneracy test."""
    spec = opt["spec"]; fstar = opt["value"]; n = spec["A"].shape[1]
    row = spec["obj"].copy(); out = []
    wv = np.zeros(n); wv[spec["pda"][list(window)]] = 1.0
    for eps in eps_list:
        rng_ = []
        for sgn in (+1, -1):
            r = run(spec, c=sgn*wv, extra_row=(row, fstar-eps, np.inf))
            rng_.append(sgn*r.fun if r.x is not None else np.nan)
        out.append(dict(eps=eps, min_pos=rng_[0], max_pos=rng_[1]))
    return out

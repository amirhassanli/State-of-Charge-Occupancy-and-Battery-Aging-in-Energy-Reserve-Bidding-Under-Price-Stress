import numpy as np, sys; sys.path.insert(0, ".")
from agingbid.core import Plant, build, optimise, settle
from agingbid.synthetic import make_panel
from agingbid.data import daily_matrices, scenarios_for_day
import pandas as pd

def _day(path):
    df = make_panel(45, path=str(path))
    from agingbid.data import load_panel
    d, c = load_panel(path); days, M = daily_matrices(d, c)
    return scenarios_for_day(M, 40, 4, np.random.default_rng(0))

def test_k1_perfect_foresight_matches_settlement(tmp_path):
    sc, real = _day(tmp_path / "synthetic.csv"); pl = Plant()
    one = {k: v[:1] for k, v in real.items()}; one = {k: np.asarray(v)[None] for k, v in real.items()}; one["prob"] = np.ones(1)
    for law in ("thr", "xu", "relcca"):
        o = optimise(pl, one, law, True, beta=0.0)
        s = settle(pl, real, law, o["bid"])
        assert abs(o["value"]-s["Wholesale"]) < 1e-4, (law, o["value"], s["Wholesale"])

def test_reserve_never_hurts_in_sample(tmp_path):
    sc, _ = _day(tmp_path / "synthetic.csv"); pl = Plant()
    for law in ("thr", "xu", "relcca"):
        assert optimise(pl, sc, law, True)["value"] >= optimise(pl, sc, law, False)["value"]-1e-6

def test_exclusive_not_better_than_relaxed(tmp_path):
    sc, _ = _day(tmp_path / "synthetic.csv"); pl = Plant()
    a = optimise(pl, sc, "thr", False)["value"]; b = optimise(pl, sc, "thr", False, exclusive=True, time_limit=60)["value"]
    assert b <= a+1e-6

def test_relcca_charge_and_discharge_gamma_are_independent(tmp_path):
    sc, _ = _day(tmp_path / "synthetic.csv")
    pl = Plant(gamma_charge_base=1.0, gamma_discharge_base=2.0)
    spec = build(pl, sc, "relcca", reserve=False)
    age = spec["sol"][0]["age"]
    assert age[1][1] == 0.8
    assert age[2][1] == 1.6

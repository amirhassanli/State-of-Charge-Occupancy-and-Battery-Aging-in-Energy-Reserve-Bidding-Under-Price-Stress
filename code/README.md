# Reconstruction model: `agingbid`

This directory is the execution entry point for the independent reconstruction. The original manuscript implementation was not supplied; this package uses SciPy's LP/MILP interface with the HiGHS solver backend. Its archived numerical results are diagnostics, not exact reproductions of the manuscript's reported tables.

See the [repository overview](../README.md) for canonical files and scientific scope, and [data provenance](../data/README.md) for input sources, scaling, and battery-data limitations.

## Environment

GitHub Actions is configured for Python 3.12–3.14. Install the pinned direct dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

`code/requirements.txt` is a convenience include for this same root dependency list.

## Tests and artifact validation

From this directory:

```bash
python -m pytest tests -q
python validate_artifacts.py
```

The tests exercise core model behavior with synthetic data. Artifact validation checks the archived source hashes, panel coverage, selected reconstruction outputs, parameter-provenance fields, VS Code tasks, and revised manuscript disclosures.

## Reproduce diagnostics

The committed panel and outputs are already archived. To write a fresh exclusive MILP cross-evaluation without overwriting them:

```powershell
python run_diagnostics.py --panel ..\data\processed\hourly_vpp_panel_2025-12-01_2026-08-21.csv --mode cross --day 2026-05-01 --K 30 --seed 20260821 --exclusive --out ..\data\results\reproduced_milp
```

Other supported modes (`cross`, `seeds`, `scan`, and `beta`) are listed by `python run_diagnostics.py --help`; the archived commands and interpretations are in [`../data/results/README.md`](../data/results/README.md). The relaxed LP permits simultaneous charge/discharge; use `--exclusive` for the binary MILP and report which formulation produced each result.

## Input data

The model expects the panel columns `timestamp, da_price, load, pv, wind` in the archived CSV under `../data/processed/`. Optional `load_fc, pv_fc, wind_fc` columns provide forecasts. Without them, the reconstruction uses persistence forecasts. Scenario errors are drawn from days no later than D−2. `agingbid/synthetic.py` is for smoke tests only; synthetic outputs are not empirical results.

The default reserve prices are four-hour block values and the default imbalance settlement is a proxy, not observed reBAP. Real-reBAP sensitivity files are separate diagnostics and do not change the default model inputs. No battery telemetry is included.

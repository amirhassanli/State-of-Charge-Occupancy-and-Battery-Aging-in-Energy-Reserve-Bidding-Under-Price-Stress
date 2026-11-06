# BESS SoC-Occupancy Aging — Energy/Reserve Bidding (Journal Article)

Reconstruction, sensitivity analysis and reproducibility package for the
manuscript *"SoC-Occupancy Aging in a Battery Energy Storage System:
Energy–Reserve Bidding under Stressed Prices"* (German DE-LU market).

## Layout

```
.
├── code/agingbid/          # core LP/MILP model (core.py) + data helpers (data.py)
├── data/
│   ├── parameters/        # battery_model.json (manuscript + code-assumption params)
│   ├── processed/         # archived public panel (SMARD/Energy-Charts, 6,319 hourly rows)
│   ├── raw/               # real market data: reBAP + aFRR activation (netztransparenz.de)
│   └── results/           # archived reconstruction outputs (CSV) + README index
├── *.docx                 # manuscript (FINAL_SUBMISSION + backups)
└── tools/git/             # portable Git (not part of the project)
```

## Run

```bash
cd code
python -m agingbid...   # see run_diagnostics.py for modes: cross / seeds / scan / beta
```

Key scripts (in `C:\Users\<you>\AppData\Local\Temp\opencode\` during development;
archived copies recommended under `scripts/`):
- `sensitivity_runs.py`        — equal-cost calibration + imbalance-proxy sensitivity
- `soc_tau_endcond.py`         — SoC-boundary / tau / end-condition sensitivity
- `real_rebap_runs.py`        — real reBAP settlement test
- `rolling_origin_runs.py`     — rolling-origin (chained terminal-SoC) evaluation

## Data sources

- Public German market & physical data: Bundesnetzagentur | SMARD, Fraunhofer ISE Energy-Charts.
- Real balancing data: netztransparenz.de (reBAP + activated aFRR, downloaded via the
  LotesCharts CsvDownloadHandler endpoint; see `data/raw/`).
- Battery aging datasets (recommended for gamma/kappa calibration):
  Sandia Preger 2020 (batteryarchive.org), Keil 2016, Schimpe 2018.

## Reproducibility

Seed `20260821`, day `2026-05-01`, MILP `K=30` unless stated. Original source code
and exact run configuration were not supplied; reconstruction uses SciPy MILP (HiGHS).
See manuscript Section VIII "Limitations of reproducibility".

## License
Code: MIT. Data: as per original providers (SMARD CC BY 4.0, netztransparenz.de terms).

# Core-model audit package: SoC occupancy aging and SMARD prices

## What this package does

This package adds a reproducible, full-history **battery-only ex-post falsification experiment** to the paper. It reads `SMARD_data_2021_2026.csv`, keeps Berlin-local market days with 23, 24, or 25 hourly observations, and solves three paired daily mixed-integer linear dispatch models:

1. Throughput aging cost.
2. Convex daily depth-of-discharge (Xu-style) aging cost plus throughput.
3. ReLCCA hourly SoC-occupancy cost plus throughput.

All three models use the same realized DA price path for each day. Binary mode variables prohibit simultaneous charging and discharging. The script exports day-level results, yearly price-regime counts, event-study summaries, a ReLCCA occupancy-coefficient sweep on all deep-negative-price days, and a 30-day moving-block bootstrap for paired daily profit differences.

## Important interpretation boundary

This is **not** a forecast, a day-ahead bid backtest, an energy–reserve co-optimization, or a realized VPP profit calculation. It uses realized prices with perfect foresight and intentionally isolates the aging-cost component. It excludes aFRR capacity revenue, activation trajectories, reBAP settlement, generator dispatch, and VPP residual-load interactions. Its profit values must not be compared directly with the main paper's coupled energy–reserve model. Its role is to falsify any broad claim that occupancy pricing by itself necessarily increases battery arbitrage profit.

## Run

Requirements: Python 3.10+, `numpy`, `pandas`, `scipy`, `matplotlib`, `python-docx` (only needed to rebuild the manuscript).

```bash
pip install numpy pandas scipy matplotlib python-docx
python run_core_model_audit.py
```

The script expects `SMARD_data_2021_2026.csv` in the same directory and writes outputs to `core_model_audit_results/`.

To rebuild the updated Word manuscript, keep `4-1_literature_expanded.docx` beside `upgrade_manuscript.py` and run:

```bash
python upgrade_manuscript.py
```

## Main computed results

- 49,655 hourly records; 2,069 local market days solved; 0 failed days.
- 1,963 negative-price hours; 118 hours at or below −50 EUR/MWh.
- 351 days with minimum DA price below zero; 37 days with minimum DA price at or below −50 EUR/MWh.
- Mean ReLCCA minus throughput ex-post profit: −€20.51/day; 30-day moving-block 95% interval [−€20.90, −€20.16].
- On the 37 deep-negative-price days, mean ReLCCA minus throughput: −€17.10/day.
- Across ReLCCA occupancy-coefficient multipliers 0.1× to 10×, the paired difference stays negative on all 37 deep-negative-price days.
- No simultaneous charge/discharge appears in the solved MILPs.

The manuscript presents these as a boundary/falsification test, not as evidence against the possibility that occupancy costs change first-stage positions in the full coupled VPP/reserve model.

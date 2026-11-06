# Gate 10 — paper extension (built on frozen baseline)

**Do not modify** `../Gate10_REAL_RESULTS/` or `../Gate10_REAL_RESULTS_BASELINE_2026-08-21/`.
All new figures, sensitivity, statistics and IEEE tables live **only** in this folder.

## What was added (Phases A–D)

| Phase | Content | Location |
|---|---|---|
| A | 22 IEEE-style figures (PNG 300 dpi + PDF) | `figures/` |
| B | Sensitivity λ ∈ {0, 0.01, 0.02, 0.05, 0.1, 0.2} × α ∈ {0.90, 0.95, 0.99} × K ∈ {30, 50, 100} | `sensitivity/` |
| C | Wilcoxon, paired t-test, bootstrap 95% CI, Cohen's d; 14-day rolling OOS | `stats/` |
| D | Tables I–VI (CSV + LaTeX + Excel) | `tables/`, `Gate10_PAPER_RESULTS.xlsx` |

## Headline result (operating day 2026-08-19, SMARD DE-LU)

| Model | HiGHS | E[profit] | CVaR₀.₉₅ | Realized | Runtime |
|---|---|---:|---:|---:|---:|
| B0 EV energy-only | kOptimal | 11 498 EUR | 9 986 | 10 938 | 0.01 s |
| B2 mean–CVaR energy-only | kOptimal | 11 508 EUR | 10 027 | 10 965 | 0.17 s |
| **P1 proposed energy–reserve** | **kOptimal** | **11 992 EUR** | **10 440** | **11 487** | 0.30 s |

P1 − B0 in-sample: **+494 EUR/day** (paired t p = 2.9×10⁻⁴¹, Wilcoxon p = 7.5×10⁻¹⁰, Cohen's d = 6.29).  
14-day rolling OOS: P1 beats B0 **every day**, mean gap **+563 EUR/day** (d = 9.39).

## Data

Bundesnetzagentur | SMARD.de via Energy-Charts API, **CC BY 4.0**, bidding zone DE-LU.
Hourly DA prices, load, solar, wind onshore/offshore and day-ahead forecasts, scaled to a 5 MW industrial-park VPP.

## Re-run (does not touch the frozen baseline if you comment out the copy step)

```bash
python3 /home/user/src/run_pipeline.py
```

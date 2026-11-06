# Gate 10 paper extension — results report

**Baseline freeze:** `Gate10_REAL_RESULTS_BASELINE_2026-08-21/` (do not modify)  
**Operating day:** 2026-08-19 (Europe/Berlin)  
**Solver:** HiGHS (`HighsModelStatus.kOptimal` for B0, B2, P1)  
**Data:** Bundesnetzagentur | SMARD.de via Energy-Charts, CC BY 4.0  
**Wall-clock (this pipeline):** 1.3 min

## Model status

| Model | Status | E[profit] EUR | CVaR EUR | Realized EUR | Runtime s | Vars |
|---|---|---:|---:|---:|---:|---:|
| B0 | HighsModelStatus.kOptimal | 11497.86 | 9985.66 | 10938.36 | 0.011 | 216 |
| B2 | HighsModelStatus.kOptimal | 11508.28 | 10026.78 | 10964.67 | 0.173 | 7323 |
| P1 | HighsModelStatus.kOptimal | 11991.79 | 10440.13 | 11486.96 | 0.303 | 7323 |


## Interpretation (short)

- **B0** schedules against the expected scenario and is most exposed to forecast-error tails.
- **B2** hedges energy imbalance via CVaR and typically reduces left-tail losses at a modest cost in expectation.
- **P1** additionally sells reserve from battery/DG headroom that is robust across scenarios, which is the intended contribution.

Default risk parameters: λ = 0.05, α = 0.95, K = 50.

## Statistical tests (in-sample scenario profits)

| Comparison | n | Mean A (EUR) | Mean B (EUR) | Mean diff. (EUR) | Std diff. (EUR) | t | p (t-test) | Wilcoxon W | p (Wilcoxon) | Cohen's d | Boot. CI 2.5% | Boot. CI 97.5% | Sig. t (5%) | Sig. W (5%) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 − B0 | 50 | 11991.788 | 11497.863 | 493.925 | 78.560 | 44.457 | 2.883e-41 | 0 | 7.504e-10 | 6.287 | 471.113 | 514.480 | True | True |
| P1 − B2 | 50 | 11991.788 | 11508.275 | 483.513 | 76.562 | 44.656 | 2.329e-41 | 0 | 7.502e-10 | 6.315 | 460.765 | 502.346 | True | True |
| B2 − B0 | 50 | 11508.275 | 11497.863 | 10.412 | 34.366 | 2.142 | 0.03716 | 420.000 | 0.03573 | 0.303 | 1.005 | 19.964 | True | True |
| P1_OOS − B0_OOS | 14 | 12202.635 | 11639.274 | 563.361 | 59.987 | 35.139 | 2.847e-14 | 0 | 0.0001221 | 9.391 | 533.004 | 592.972 | True | True |
| P1_OOS − B2_OOS | 14 | 12202.635 | 11632.711 | 569.924 | 46.900 | 45.468 | 1.025e-15 | 0 | 0.0001221 | 12.152 | 545.994 | 593.158 | True | True |
| B2_OOS − B0_OOS | 14 | 11632.711 | 11639.274 | -6.563 | 24.017 | -1.022 | 0.3252 | 36.000 | 0.3258 | -0.2733 | -18.522 | 5.496 | False | False |

## Rolling OOS mean realized profit

| model | mean | std | min | max |
| --- | --- | --- | --- | --- |
| B0 | 11639.274 | 1589.497 | 8557.047 | 14055.846 |
| B2 | 11632.711 | 1581.549 | 8576.060 | 14070.470 |
| P1 | 12202.635 | 1569.567 | 9203.801 | 14700.644 |

All IEEE tables: `tables/`  ·  figures: `figures/` (PNG 300 dpi + PDF).

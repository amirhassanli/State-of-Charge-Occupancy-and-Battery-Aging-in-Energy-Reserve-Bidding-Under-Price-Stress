# ChronosBid Pre-Coding Study Blueprint and Reviewer Matrix

## 1. Pre-registered hypotheses

**H1 — Dependence validity.** Regime-conditioned temporal scenarios will improve held-out negative-price frequency, joint-tail, and temporal-dependence diagnostics relative to an unconditional Gaussian copula and an unconditional Student-t copula.

**H2 — Negative-price decision value.** On the pre-registered negative-price-day OOS stratum, ChronosBid will change realized profit and imbalance cashflow relative to sign-aware but regime-unconditioned benchmark P0. The direction and statistical significance will be determined from real paired observations; it is not claimed in advance.

**H3 — Reliability value.** Energy-aware N−1 constraints will reduce N−1 delivery violations and reserve shortfall relative to nominal-capacity security constraints, while quantifying the associated profit/flexibility trade-off.

**H4 — Risk value.** Increasing \(\beta\) will trace a realized profit–downside-risk frontier. The paper will report the frontier; it will not assert monotonic improvement without evidence.

## 2. Model inventory and attribution logic

| Model | Calibrated marginals | Dependence | Negative-price economics | Regime condition | Tail reduction | CVaR | Energy-aware N−1 | Attribution |
|---|---:|---|---:|---:|---:|---:|---:|---|
| B0 | No | None | Signed settlement | No | No | No | No | Deterministic base |
| B1 | No | Gaussian | Signed settlement | No | Standard | No | No | Stochasticity / Gaussian dependence |
| B2 | No | Student-t | Signed settlement | No | Standard | No | No | Heavy-tailed dependence |
| B3 | Yes | Student-t | Signed settlement | No | Standard | No | No | Calibration value |
| B4 | Yes | Student-t | Signed settlement | No | Bidirectional | No | No | Tail-reduction value |
| P0 | Yes | Student-t | Yes | No | Bidirectional | Yes | Yes | Sign-aware recourse value |
| P1 | Yes | Regime-conditioned Student-t | Yes | Yes | Bidirectional | Yes | Yes | Full ChronosBid value |

All models use the same real calendar, physical portfolio, forecast availability rule, solver limits, and settlement function.

## 3. Exact empirical outputs

### Table 1 — Data provenance and study calendar
Sources, frequency, units, coverage, hashes, and forecast-vintage availability.

### Table 2 — Negative-price incidence, depth, duration, and seasonality
Mandatory NP-1 table from `Negative_Price_Reviewer_Proof_Analysis_Plan.md`.

### Table 3 — Scenario-model validation
Marginal calibration, PIT, ACF error, correlation error, negative-price frequency error, tail co-exceedance, and runtime.

### Table 4 — Main OOS performance
Realized profit, realized CVaR, imbalance cashflow, absolute imbalance, curtailment, reserve shortfall, N−1 violations, runtime, MIP gap.

### Table 5 — Negative-price-stratum OOS performance
Same metrics restricted to pre-registered negative, deep-negative, and persistent-negative strata; always report sample sizes.

### Table 6 — Paired inference
Mean and median differences, 95% moving-block-bootstrap confidence intervals, signed-rank p-values, effect sizes, and number of paired days.

### Table 7 — Sensitivity and robustness
\(\alpha\), \(\beta\), \(K\), calibration-window length, BESS duration, and activation-duration sensitivity.

### Figure 1 — ChronosBid architecture
Already generated conceptual SVG.

### Figure 2 — Seven-gate chronology
Already generated conceptual SVG.

### Figure 3 — Negative-price duration curve and calendar heatmap
Real 2025 DA prices only.

### Figure 4 — Episode depth–duration and system-state conditional plot
Real 2025 price, renewable, load, and residual-load observations only.

### Figure 5 — Scenario diagnostics
Observed versus generated marginal, temporal, regime, and tail statistics.

### Figure 6 — OOS paired-profit and imbalance raincloud plots
Daily paired realized settlement outcomes only.

### Figure 7 — Negative-price decision decomposition
Avoided negative-price export, BESS charging, DR shift, curtailment, and imbalance cashflow.

### Figure 8 — Risk-return and N−1 trade-off frontiers
Realized OOS frontier across \(\beta\), with reserve shortfall/N−1 outcomes.

## 4. Reviewer-objection matrix

| Likely reviewer objection | Mandatory evidence / response |
|---|---|
| “Negative prices are rare or immaterial.” | Table 2 plus Figs. 3–4: hours, days, episodes, depth, persistence, seasonality, and system state. |
| “The model clips or mishandles negative prices.” | Signed-price equations, raw-data sign audit, and Fig. 7 decomposition. |
| “The Student-t copula is incremental.” | Regime-conditioning ablation P1 vs. P0, bidirectional-tail reduction, and decision-level OOS evidence. |
| “Scenario quality does not prove economic value.” | Separate Table 3 from Tables 4–6; make claims only from paired realized settlements. |
| “Results may leak future information.” | Forecast-vintage table, issue/gate timestamp audit, frozen rolling OOS calendar, and code log. |
| “The VPP is not physically credible.” | Locked asset portfolio, SOC/ramping/DR constraints, energy-aware N−1, and reserve activation duration. |
| “Imbalance settlement is simplified.” | Native reBAP data, documented sign mapping, no double-counting audit, and 15-min settlement rule. |
| “Results are driven by arbitrary scaling.” | Real asset data or transparent capacity-calibrated representative portfolio, never profit-tuned scaling. |
| “Tail results are cherry-picked.” | Pre-registered strata, thresholds, seeds, OOS dates, and all-model reporting. |
| “Computation is impractical.” | K-runtime frontier, solver limit, MIP gap, hardware, and scenario-count selection on validation only. |

## 5. Stop/go gates

### Gate A — Scope lock
Market products, DA/ID/reserve/balancing scope, real asset availability, and contract treatment approved.

### Gate B — Raw data lock
2024 warm-up and 2025 frozen OOS snapshots collected; manifest and hashes produced.

### Gate C — Forecast eligibility
Every forecast has issuance/gate metadata; any ineligible value blocks the corresponding OOS date.

### Gate D — Market settlement lock
Negative price, reBAP, reserve, and remuneration sign/accounting mappings independently checked.

### Gate E — Scenario validation
Regime, marginal, temporal, and tail metrics reported on validation data before OOS model comparison.

### Gate F — Main OOS execution
All benchmark decisions frozen and settled over the same complete calendar.

### Gate G — Statistical reporting
Paired bootstrap/Wilcoxon, effect sizes, strata sample counts, sensitivity, and reproducibility manifest complete.

No gate can be skipped because a later output appears favorable.

## 6. Submission-safe claims

### Claims allowed before final OOS execution

- ChronosBid proposes a regime-conditioned negative-price-aware sequential VPP bidding framework.
- The framework is designed for German market conditions with signed price and imbalance settlement.
- The protocol distinguishes statistical scenario fidelity from realized decision value.
- The model enforces energy-aware N−1 reserve deliverability.

### Claims prohibited before final OOS execution

- ChronosBid improves profit.
- ChronosBid reduces imbalance cost.
- ChronosBid outperforms Gaussian or deterministic benchmarks.
- Regime conditioning is statistically/economically significant.
- N−1 security has a specified economic cost.

## 7. Immediate next action sequence

1. Lock study scope and select real-market products that have accessible real settlement data.
2. Create the exact raw-source acquisition list and file manifest template.
3. Acquire 2024 warm-up and 2025 frozen OOS source snapshots once.
4. Run data-quality gates before any model/forecast/scenario code.
5. Implement only after Gates A–D pass.

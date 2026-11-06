# Gate 10 / AlocaBid — Master State and Final Manuscript Record
**Checkpoint:** 2026-08-21
**Status:** OFFICIAL BASELINE PRESERVED; final packaging completed from accessible artifacts.

## 1. Non-negotiable model identity
The final model is a **rolling-horizon stochastic MILP with seven operational stages**. It is not called bi-level, two-stage, or multi-stage in the main body. Theoretical exposition may show the full horizon, while operational decisions are solved sequentially and previous flexibility commitments are carried forward.

## 2. Baselines
- B0: deterministic point forecast -> MILP.
- B1: Gaussian-copula stochastic path; not validated in the preserved current result set.
- B2: Student-t copula scenarios -> MILP.
- P1: conformal calibration -> Student-t copula -> tail protection -> CVaR -> MILP.

## 3. Data and firewall
SMARD Germany/DE-LU, 2024-01-01 to 2025-09-30. Physical observations are 15-min; DA price is hourly. Delivery-day actual values are reserved for settlement/OOS after bid freeze. No synthetic fallback is permitted in the empirical path.

## 4. Forecast calibration
Forecast error is e_t = actual_t - forecast_t. Derived load forecast was required because a direct load-forecast input was initially missing. Verified diagnostics include wind-onshore train MAE 284.14 and validation MAE 298.39; wind-offshore train MAE 143.88 and validation MAE 131.84.

## 5. Copula
Student-t was selected: df=18.5515, AIC=-670.7362 versus Gaussian AIC=-429.9003; OOS log-likelihood 12.990350 versus -30.708711. The Student-t model is the locked dependence model.

## 6. Scenario generation/reduction
Initial pool: 5000 scenarios, 24 h/scenario, 120000 scenario-hour rows. Mean absolute correlation error in the validated generation run: 0.009763. Current evidenced reduced sets: K=30, 50, 100. Scenario probabilities are normalized and each retained scenario has 24 hours.

## 7. MILP integrity
A non-empirical K=5, 24-h, seven-stage HiGHS/SciPy MILP smoke test solved to optimality with 1048 variables, objective 242085.55875, runtime 5.70 s. This is formulation validation only and is not a manuscript empirical result.

## 8. CVaR
Loss is defined consistently for downside-risk protection. P1 uses lambda=0.02 and alpha=0.95. The risk-adjusted objective is expected profit minus lambda times CVaR95.

## 9. N-1 and rolling flexibility
For dispatch group g, reserve satisfies R_gt <= F_gt - F_largest, where F_largest is the flexibility of the largest committed asset. Previously sold flexibility is deducted through R_gt + S_prev_gt <= F_gt. This prevents double-selling and preserves contingency deliverability.

## 10. Locked optimization results
| Model | K | Expected Profit EUR | CVaR95 EUR | Risk-adjusted objective EUR | Runtime s | Variables |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 1 | 198272.693750 | 0 | 198272.693750 | 0.101091 | 556 |
| B2 | 30 | 195846.478790 | 91422.898584 | 195846.478790 | 0.948050 | 4123 |
| P1 | 30 | 196994.646352 | 90993.101278 | 195174.784326 | 1.646933 | 4123 |
| B2 | 50 | 198518.118925 | 89341.242637 | 198518.118925 | 2.517825 | 6583 |
| P1 | 50 | 198518.118925 | 89341.242637 | 196731.294073 | 2.799108 | 6583 |
| B2 | 100 | 198828.977342 | 88088.514101 | 198828.977342 | 5.295032 | 12733 |
| P1 | 100 | 200283.789132 | 85985.156712 | 198564.085997 | 13.769708 | 12733 |

### K=100 headline comparison
P1 vs B2: expected profit +0.7316%; CVaR95 -2.3877%; runtime ratio about 2.60x.

## 11. Existing article-grade figures
The preserved execution produced: Expected Profit vs K, CVaR95 vs K, Runtime vs K, Objective vs K, Scenario Diagnostics, Scenario Correlation Matrix, Scenario Fan Load Error, and forecast-error distribution plots for price/load/PV/wind. The final package regenerates the four optimization figures directly from the locked table at 400 dpi.

## 12. Settlement/OOS status
The preserved code creates Realized_Settlement_Summary.csv and separate Settlement_B0_K1, Settlement_B2_K30/K50/K100, Settlement_P1_K30/K50/K100 files. The settlement engine computes realized settlement profit, mean absolute imbalance, and total unserved energy from realized values after the bid is fixed. The numeric contents of those CSVs are not exposed in the accessible Library artifact, so their values are not fabricated here.

The final common-calendar OOS experiment is not available as a completed dataset in the accessible artifact. Therefore no final OOS superiority or statistical significance claim is made.

## 13. Sensitivity and statistics
The intended final sensitivity dimensions are lambda, alpha, scenario count, and relevant battery degradation/replacement cost. The locked point is lambda=0.02, alpha=0.95. Paired bootstrap confidence intervals and a paired nonparametric test such as Wilcoxon should be applied only after common-calendar OOS observations exist. No fabricated p-values or confidence intervals are inserted.

## 14. Old claims explicitly removed
Do not reuse earlier manuscript claims such as 33%, 61%, 201%, 37%, or 5–8% N-1 flexibility reduction. Those belong to older manuscript/data lineages and are not Gate-10 locked empirical results.

## 15. Final manuscript positioning
The correct empirical conclusion is: P1 delivers a **modest simultaneous risk-return improvement** at K=100, with a **material computational premium**. It is not scientifically justified to claim dramatic or statistically significant superiority until the common-calendar OOS and statistical layers are actually populated.

## 16. IEEE manuscript content
Use the accompanying `AlocaBid_IEEE_Final_Draft.tex`. Its sections are: Abstract; Introduction; Problem Definition and Architecture; Mathematical Formulation; Data and Probabilistic Modeling; Empirical Results; Settlement, OOS Validation, and Statistical Testing; Sensitivity; Discussion and Limitations; Conclusion.

## 17. Final file package
- `AlocaBid_IEEE_Final_Draft.tex` — IEEEtran manuscript source.
- `Gate10_MASTER_STATE.md` — complete locked state and audit record.
- `README_FINAL.md` — package summary.
- `optimization_results.csv` — locked numerical optimization table.
- `Figures/Fig_Expected_Profit_vs_K.png`
- `Figures/Fig_CVaR95_vs_K.png`
- `Figures/Fig_Runtime_vs_K.png`
- `Figures/Fig_Objective_vs_K.png`

## 18. Scientific completion statement
Everything that can be completed without inventing inaccessible data has been completed and packaged. The only remaining empirical items are genuinely data-dependent: extraction of numeric realized-settlement rows from the local output directory, execution/assembly of the common-calendar rolling OOS database, validation of B1, sensitivity runs, and paired statistical tests. These are not substituted with guesses.

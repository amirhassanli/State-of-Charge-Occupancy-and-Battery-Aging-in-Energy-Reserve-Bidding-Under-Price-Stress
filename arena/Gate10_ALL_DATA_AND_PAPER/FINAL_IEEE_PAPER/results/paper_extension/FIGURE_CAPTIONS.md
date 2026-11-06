# Gate 10 — Figure captions (IEEE style)

Operating day: **2026-08-19**. Data: Bundesnetzagentur | SMARD.de (CC BY 4.0) via Energy-Charts.

- **Fig. 1.** Day-ahead forecast versus realized SMARD series (price, VPP load, PV, wind) on the operating day.
- **Fig. 2.** Hourly profit trajectories (in-sample mean and P10–P90 band) for B0, B2 and P1.
- **Fig. 3.** Daily profit comparison: in-sample expectation (error bar = scenario std.) versus realized out-of-sample settlement.
- **Fig. 4.** Expected profit versus empirical CVaR$_{0.95}$ of the scenario profit distribution.
- **Fig. 5.** HiGHS wall-clock runtime versus the number of scenarios $K$.
- **Fig. 6.** Scenario fan charts obtained by daily block-bootstrap of forecast errors.
- **Fig. 7.** Correlation matrix of selected-hour forecast errors (price, load, PV, wind).
- **Fig. 8.** Kernel density estimates of day-ahead forecast errors.
- **Fig. 9.** Box-plot of in-sample scenario profits.
- **Fig. 10.** Violin plot of in-sample scenario profits.
- **Fig. 11.** Empirical CDF of in-sample scenario profits.
- **Fig. 12.** Multi-criteria radar (min–max normalised across models).
- **Fig. 13.** Battery state of charge (in-sample mean / P10–P90 and realized recourse).
- **Fig. 14.** Distributed-generation dispatch.
- **Fig. 15.** Day-ahead reserve allocation (P1; B0/B2 have zero reserve).
- **Fig. 16.** Net energy imbalance (long positive, short negative).
- **Fig. 17.** Row-normalised heatmap of P1 24-hour first- and second-stage decisions.
- **Fig. 18.** P1 sensitivity to the mean–CVaR weight $\lambda$ ($\alpha=0.95$, $K=50$).
- **Fig. 19.** P1 sensitivity to the CVaR confidence $\alpha$ ($\lambda=0.05$, $K=50$).
- **Fig. 20.** Rolling out-of-sample realized daily profit (14-day window).
- **Fig. 21.** Profit–risk scatter (expectation and CVaR versus scenario std.).
- **Fig. 22.** Day-ahead energy position (sell positive) against the realized DA price.

Models: **B0** expected-value deterministic energy-only; **B2** two-stage mean–CVaR energy-only; **P1** proposed two-stage mean–CVaR joint energy–reserve co-optimisation.

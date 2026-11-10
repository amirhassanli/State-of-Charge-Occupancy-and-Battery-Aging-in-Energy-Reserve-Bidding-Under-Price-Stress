# E1–E12 identification tests (reconstruction)

Run from this folder, e.g. `python e05_tau_sweep.py`. Uses `code/agingbid/core.py` and the archived panel.
All numbers are **reconstruction** outputs (relaxed LP, K=30 unless stated), not the original model.
Override paths with `AGINGBID_REPO` / `AGINGBID_PANEL`.

| Script | Test |
|---|---|
| e01 | reserve cap: per-direction vs aggregate |
| e02 | 3x3 position-valuation matrix |
| e03 | Exclusive-MILP figure: p_DA, r_up, r_dn, and scenario-mean SoC |
| e04 | {optimise proxy/reBAP} x {settle proxy/reBAP}; reBAP-optimise cell is LEAKY (realised reBAP) |
| e05 | tau sweep with effective reserve |
| e06 | value function V(kappa), V(c_thr) |
| e07 | solver tolerance 1e-7 vs 1e-9, eps-optimal position range |
| e08 | 20-day scan, aFRR vs energy-side decomposition |
| e08_plot_scan.py | 300-dpi plot of the committed 20-day scan CSV |
| e09 | equal-cost calibration + TOST |
| e10 | reserve-price robustness (auction CSV hook) |
| e11 | +-25% load/PV/wind scale |
| e12 | alpha, K, beta grid |

`results/` holds the CSV/PNG outputs of the runs made in this session.

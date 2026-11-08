# Reconstructed Diagnostic Outputs

These outputs were generated from the archived public panel and the reviewer-facing reconstruction in `code/agingbid/`. They are **not** the original manuscript outputs and must not be substituted into Tables III-VI without recovering the original source code and exact parameter set.

## Runs

- `ablation/ablation_cross_2026-05-01.csv`, `ablation/ablation_gaps_2026-05-01.csv`: component ablation on the archived K=30 MILP cross design (1 May, seed 20260821). Same-law P1-B2 differentials: full ReLCCA -102.45, calendar-only (relcca_cal) -91.63, calendar removed (relcca_cyc, i.e., kappa -> 0) -98.57, throughput -98.73, Xu -97.20 EUR. The sign stays negative under every calendar/cycle weighting; the reconstruction's non-reproduction is insensitive to the SoC-occupancy term. Output written by the session ablation script (Temp workspace).

- `cross_2026-05-01.csv`, `overlap_2026-05-01.csv`, `epsrange_2026-05-01.csv`: 1 May 2026 cross-evaluation with binary charge/discharge exclusivity (`--exclusive`), K=30, seed 20260821. This is the MILP run.
- `relaxed_lp/`: same 1 May design without binary exclusivity. This is the relaxed LP and permits simultaneous charge/discharge.
- `negative_scan_lp/scan.csv`: all days with minimum day-ahead price below -20 EUR/MWh, relaxed LP, K=20, seed 20260821.
- Scenario-count sweep (reconstruction, 1 May 2026, MILP, seed 20260821; reference assumptions E0 = 2.5 MWh and tau = 1 h): the P1-B2 wholesale gaps stay negative for all three aging laws at K = 30, 50, 100, and 200 (throughput: -98.7 to -280.7; Xu: -97.2 to -253.1; ReLCCA: -102.5 to -253.5 EUR). The gap magnitude does not converge: the MILP schedule itself changes with the scenario sample, so the controlled diagnostic is sign stability conditional on the reference assumptions. Sweep outputs are in `Temp\opencode\scenconv\K{30..200}` (session workspace, regenerate with the cross command above and `--K <K>`).

## Selected Same-Law P1-B2 Results

Wholesale EUR under each bid's own aging law, settlement recourse re-optimized under the same law:

| Run | Throughput | Daily DoD | ReLCCA |
|---|---:|---:|---:|
| 1 May relaxed LP | -321.35 | -236.99 | -244.70 |
| 1 May exclusive MILP | -98.73 | -97.20 | -102.45 |

The relaxed LP has substantial simultaneous charge/discharge: up to 11.99 MWh in a scenario.

The archived reconstruction outputs were independently re-run from the committed panel, scenario count, and seed 20260821 in a clean environment: the 1 May cross-evaluation (MILP and relaxed LP) and the 20-day event scan regenerate without numerical deviation (max |difference| < 1e-9 EUR). On the event scan, each aging law yields 2 reversals among 20 qualifying days; the corresponding reversal rate has a Wilson 95% interval of [0.028, 0.301] and a Clopper-Pearson interval of [0.012, 0.317]. A paired comparison of ReLCCA and throughput differentials on those days shows no statistically distinguishable systematic advantage (mean gap -3.81 EUR, Wilcoxon p = 0.330). The checked-in `agingbid.stats.paired_summary` uses a moving-block bootstrap with block length 7, 4,000 replicates, and seed 0; it returns a 95% interval of [-8.30, +1.14] EUR. The previously quoted [-9.78, +1.24] interval used block lengths 3-9, but its exact resampling implementation is not present in the package and it is not reported in the revised manuscript. The ReLCCA differential is the largest of the three aging laws on only 6 of 20 days. The exclusive MILP removes simultaneous charge/discharge overlap, but produces materially different P1-B2 values. The manuscript's original result is therefore not validated by these reconstructions.

The negative-price scan found 2 reversals among 20 qualifying days for each of the three aging laws under this reconstruction. These are an in-sample diagnostic count, not a population probability; the interval estimates and paired test are in the console output from the task run and can be regenerated with the command below.

## Reproduction Commands

Run from the `code` directory:

```powershell
python run_diagnostics.py --panel ..\data\processed\hourly_vpp_panel_2025-12-01_2026-08-21.csv --mode cross --day 2026-05-01 --K 30 --seed 20260821 --exclusive --out ..\data\results
python run_diagnostics.py --panel ..\data\processed\hourly_vpp_panel_2025-12-01_2026-08-21.csv --mode cross --day 2026-05-01 --K 30 --seed 20260821 --out ..\data\results\relaxed_lp
python run_diagnostics.py --panel ..\data\processed\hourly_vpp_panel_2025-12-01_2026-08-21.csv --mode scan --K 20 --seed 20260821 --out ..\data\results\negative_scan_lp
```

The code-only assumptions are catalogued in `data/parameters/battery_model.json`; no measured battery telemetry or cell-level data were downloaded or used.
- `sensitivity/equal_cost_calibration_2026-05-01.csv`: equal-cost-at-reference calibration (M3 response). Coefficients of each law rescaled so the B2 daily aging cost at the 1 May reference dispatch equals the 3-law mean (29.49 EUR/day); scale factors thr 1.636, Xu 0.776, ReLCCA 0.909. Same-law MILP P1-B2 gaps after calibration: throughput -110.80, Xu -99.46, ReLCCA -102.47 EUR (cycle-halved ReLCCA variant: -90.60). Ranking and signs unchanged vs base (-98.73 / -97.20 / -102.45).
- `sensitivity/imbalance_proxy_sensitivity_2026-05-01.csv`: imbalance-proxy sensitivity (M7 response), 1 May MILP, K=30, seed 20260821. P1-B2 gaps (thr/Xu/ReLCCA, EUR): base spread -98.73 / -97.20 / -102.45; half-spread -102.73 / -97.24 / -109.19; zero spread (single-price settlement, no deterministic arbitrage) -119.07 / -112.92 / -96.10. All values remain negative; the proxy-arbitrage concern does not flip the sign.
- Update on the scan interpretation: relaxed-LP scan gaps are positive on 18 of 20 qualifying days for every law (two reversals each); the reconstruction therefore reproduces the dominant scan pattern, and only the reversal counts differ from the original report.
- `sensitivity/soc_tau_endcond_sensitivity_2026-05-01.csv`: SoC-boundary / reserve-sustainment / end-condition sensitivity (1 May MILP, K=30, seed 20260821). P1-B2 gaps (thr/Xu/ReLCCA, EUR): base (E0 = 2.5 MWh, tau = 1 h) -98.73/-97.20/-102.45; E0 = 1.5 MWh -87.17/-80.27/-93.27; E0 = 3.5 MWh -97.06/-91.58/-102.35; free terminal energy -53.50/-37.67/-55.15; tau = 2 h +16.88/-6.98/+70.04; tau = 4 h +428.19/+438.59/+428.19. The differential sign is stable across the recorded initial-SoC levels and a free terminal-energy boundary, but reverses for some or all laws at tau >= 2 h; the reconstruction's negative differential is therefore conditional on the unstated tau = 1 h assumption. The archived CSV's `e0_MWh` values (1.5 and 3.5) are used here; variant labels in the output do not match those values.
- Body docx updates accompanying the above: explicit E0 = 2.5 MWh (mid-band, cyclic start/end) and tau = 1 h disclosed in the battery-model and reproducibility limitations; new Table VII row 'Reserve-sustainment tau and SoC-boundary variants'; provisional-conclusions sentence extended accordingly; Table VI caption notes that per-row scenario-count settings are not stated in the available materials.
- `sensitivity/real_rebap_sensitivity_2026-05-01.csv`: real-reBAP settlement test (M7/M12). Real reBAP for 1 May 2026 from netztransparenz.de (mean 89.9, range -394.6 to 1489.7 EUR/MWh); aFRR activation volume 2,929 MWh positive / 935 MWh negative. P1-B2 gaps (thr/Xu/ReLCCA, EUR): hybrid (proxy optimize, real settle) -1823.5/-1831.5/-1887.7; full real-data +879.96/+882.39/+878.32. The 1 May sign reverses under full real-data settlement: the proxy, not the aging law, is the binding limitation.
- `sensitivity/rolling_origin_2026.csv`: contiguous 20-day evaluation (1-20 Aug 2026, K=30). P1-B2 positive on all 20 days for all three laws (cumulative +23,105/+23,269/+23,016 EUR); sign opposite to the negative-price regime. Daily cyclic boundary reset each day.
- `data/battery_calibration_sources.md`: recommended public aging datasets for gamma/kappa calibration (Sandia Preger 2020, Keil 2016, Schimpe 2018, CALCE, Oxford).
- `sensitivity/b4_b5_b6_sensitivity_2026-05-01.csv`: B4/B5/B6 on 1 May (MILP, K=30). B4 reserve-cap aggregation: per-direction caps give -98.7/-97.2/-102.5 EUR; aggregate cap (r_up+r_down<=1.5) gives +67.4/+87.2/+76.0 EUR and cuts aFRR revenue from ~1384 to ~920 EUR -> the aggregation rule alone flips the sign. B5 3x3 position-valuation matrix: fixing each law's bid and valuing under all three laws gives a 4447-4469 EUR range (~18 EUR spread); the aging law barely moves the optimal position. B6 tau=0.5 h: gaps +499/+483/+494 EUR (vs tau=1: -98.7/-97.2/-102.5). Missing 2x2 cell (optimize reBAP, settle proxy): -32478/-32487/-32500 EUR (catastrophic cross-settlement).
- `manuscript`: added Table VIII (2x2 settlement decomposition), Fig. 1/Fig. 4 captions labelled unverified, consolidated limitations paragraph, F1/F2/F4/F5 text fixes, conclusion changed from 'provisional' to 'not supported', P98 causal claim softened, P73/P110 self-reconstruction framing.
- `sensitivity/kappa_sweep_2026-05-01.csv`: E6 kappa sweep (0.1x to 10x base). P1-B2 gaps stable: thr ~-98.7, xu ~-97.2, relcca -98.3 to -102.5. Structural aging effect is minimal even at 10x kappa (~4 EUR difference between laws).
- `sensitivity/load_scaling_2026-05-01.csv`: F7 load scaling ±25% (1 May, MILP, K=30). P1-B2 gaps: scale 0.75 -> -73.9/-68.1/-80.3; scale 1.0 -> -98.7/-97.2/-102.5; scale 1.25 -> -109.4/-104.4/-105.6 EUR. Variation ~±10-15 EUR, small vs 2,703 EUR settlement effect.
- `sensitivity/rebap_20days_scan.csv`: E4 real reBAP settlement over all 20 scan days. Proxy cumulative +19,639 EUR vs real reBAP +9,424 EUR; real reBAP halves the differential, flips sign only on 1 May (-1,796 EUR real vs -95 EUR proxy).
- `sensitivity/zero_reserve_revenue_20days.csv`: E8 zero reserve revenue -> P1-B2 = 0 on every day (cumulative 0 EUR). Reserve revenue alone explains the entire differential.

# Reconstructed Diagnostic Outputs

These files are outputs of the independent reconstruction in `code/agingbid/`. They are not the original study outputs and must not be presented as an exact reproduction of the manuscript's reported Tables III–VI.

## Reproducible runs

| Output | Formulation and use |
|---|---|
| `cross_2026-05-01.csv`, `overlap_2026-05-01.csv`, `epsrange_2026-05-01.csv` | 1 May 2026, exclusive charge/discharge MILP, K = 30, seed 20260821 |
| `relaxed_lp/cross_2026-05-01.csv`, `relaxed_lp/overlap_2026-05-01.csv`, `relaxed_lp/epsrange_2026-05-01.csv` | Same date and scenario settings, without binary charge/discharge exclusivity; simultaneous charging and discharging are feasible |
| `negative_scan_lp/scan.csv` | Relaxed-LP scan of the 20 panel days with minimum day-ahead price below −20 EUR/MWh; K = 20, seed 20260821 |
| `ablation/ablation_cross_2026-05-01.csv`, `ablation/ablation_gaps_2026-05-01.csv` | Exclusive-MILP component ablation on 1 May |
| `../../code/e_tests/results/` | E1–E12 identification-test outputs; settings and interpretation are documented in `../../docs/E_tests_findings.md` |

The exclusive-MILP P1−B2 wholesale gaps on 1 May are −98.73/−97.20/−102.45 EUR for throughput/Xu/ReLCCA. In the relaxed LP they are −321.35/−236.99/−244.70 EUR, with up to 11.99 MWh of daily-summed simultaneous charge/discharge in a scenario. The scan has two sign reversals among 20 days for each aging law; this is an in-sample diagnostic count, not a population event rate.

## E4: optimization input is not the settlement rule

`../../code/e_tests/results/E04_settlement_2x2.csv` is the current crossed E4 result (relaxed LP, 1 May, K = 30). Gaps below are P1−B2 in EUR, ordered throughput/Xu/ReLCCA:

| Optimization input | Settlement | Gaps |
|---|---|---:|
| Proxy | Proxy | −321.35 / −236.99 / −244.70 |
| Proxy | Observed reBAP | −1,927.52 / −1,964.21 / −1,943.86 |
| Realized reBAP (LEAKY) | Proxy | +339.12 / +313.74 / +335.07 |
| Realized reBAP (LEAKY) | Observed reBAP | +848.45 / +839.25 / +844.56 |

The realized-reBAP optimization cells pass the same day's realized imbalance prices to the optimizer. They have perfect foresight and are **LEAKY**, not ex-ante bids. Comparing the two rows settled under reBAP changes both the optimization input and the resulting bid; their difference is not a pure settlement effect. The aging-law order also changes in this crossed comparison, but this leaky comparison does not establish a general ranking or a ReLCCA advantage.

`sensitivity/real_rebap_sensitivity_2026-05-01.csv` is a separately archived, earlier sensitivity output. Its optimization settings and values do not match the current E4 script/output above. Do not combine it with E4 or use its 2,703-EUR contrast as a settlement-only effect.

## Other archived sensitivities

The following CSVs are supporting outputs, not substitutes for the E1–E12 results:

- `sensitivity/b4_b5_b6_sensitivity_2026-05-01.csv`: reserve-cap interpretation, position-valuation matrix, and reserve-duration variants.
- `sensitivity/equal_cost_calibration_2026-05-01.csv`: equal-cost calibration under the exclusive MILP.
- `sensitivity/imbalance_proxy_sensitivity_2026-05-01.csv`: proxy-spread variants; some extreme zero-spread solutions are sensitive to position bounds and should be interpreted with the full CSV.
- `sensitivity/rolling_origin_2026.csv`: archived contiguous August evaluation; each day resets the cyclic battery boundary.
- `sensitivity/soc_tau_endcond_sensitivity_2026-05-01.csv`: initial-SoC, terminal-energy, and reserve-sustainment variants.

Not every archived sensitivity has a maintained generation script in the current repository. Treat a result as independently reproducible only when its script, inputs, and settings are available.

## Reproduction commands

Run from the `code` directory:

```powershell
python run_diagnostics.py --panel ..\data\processed\hourly_vpp_panel_2025-12-01_2026-08-21.csv --mode cross --day 2026-05-01 --K 30 --seed 20260821 --exclusive --out ..\data\results
python run_diagnostics.py --panel ..\data\processed\hourly_vpp_panel_2025-12-01_2026-08-21.csv --mode cross --day 2026-05-01 --K 30 --seed 20260821 --out ..\data\results\relaxed_lp
python run_diagnostics.py --panel ..\data\processed\hourly_vpp_panel_2025-12-01_2026-08-21.csv --mode scan --K 20 --seed 20260821 --out ..\data\results\negative_scan_lp
```

The code-only assumptions are catalogued in `../parameters/battery_model.json`. The repository contains no measured battery telemetry, chemistry-specific test series, or temperature history.

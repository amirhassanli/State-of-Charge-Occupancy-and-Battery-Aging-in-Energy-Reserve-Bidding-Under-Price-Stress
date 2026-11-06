# Reproducibility (final)

Paper: `Hassanli_Abbasi_Occupancy_Aging_IEEE.html` / `.docx`  
Title: **When Occupancy Aging Changes a CVaR Energy–Reserve Bid: A SMARD Diagnostic**  
Every euro is a recorded HiGHS `kOptimal` solve. Seed `20260821`.

## Data

- Bundesnetzagentur | SMARD.de via `api.energy-charts.info` (CC BY 4.0).
- Fetch: `src/fetch_smard_expand.py` → `data/raw/smard_*.csv`
- Panel: 1 Dec 2025 – 21 Aug 2026 Berlin.
- Scale (frozen Gate-10): `sf_load=8.279727445448033e-05`, `sf_pv=6.889955779402563e-05`, `sf_w=4.810120493518363e-05`.

aFRR: published DE 4-hour block means in `src/xu_pwl_model.py:apply_afrr_block_prices`. Same schedule on every day. Not a cleared tape. Energy-Charts has no aFRR/reBAP endpoint. ENTSO-E returns 401 without a token.

Imbalance: two-price proxy in `gate10_core._imb_prices` (short = DA+18+0.12|DA|, long = DA−10−0.08|DA|). Not reBAP.

## Solves

| Script | Writes |
|---|---|
| `src/calibrate_kappa.py` | `stats/kappa_ols.json` (3 Keil plateaus → κ) |
| `src/run_multiseason.py` | isolation / weeks / LFP / r_max |
| `src/run_soh_bootstrap.py` | bootstrap CI, SoH week |
| `src/run_review7_rest.py` | OLS isolation, injection, 24 May decompose |
| `src/run_review_apply4.py` | 20-day scan, cal/cyc split, K check |
| `src/run_final_sensitivity.py` | N-band and κ assignment |
| `src/relcca_model.py` | ReLCCA LP; simplex → IPM fallback |

Do not reuse `regime_scan.csv` row `2026-05-24` B2-ReLCCA (failed settlement). Recovered numbers are in `review7_decompose.csv`.

## What is not claimed

No public GitHub/Zenodo URL (this sandbox has no remote). The local package is the reproduction path: `src/`, `data/`, `Gate10_PAPER_EXTENSION/stats/`, `FINAL_IEEE_PAPER/code/`.

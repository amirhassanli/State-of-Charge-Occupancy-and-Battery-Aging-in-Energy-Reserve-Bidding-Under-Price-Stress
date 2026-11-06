# Code, data, figures, and what was run

Authors: Amir Hassanli, Ali Reza Abbasi.  
Deliverable paper: `Hassanli_Abbasi_Occupancy_Aging_IEEE.html` / `.docx`

---

## 1. Data (all CC BY 4.0 unless noted)

| File | Source | Coverage |
|---|---|---|
| `data/raw/smard_da_prices_de_lu.csv` | Energy-Charts API `price?bzn=DE-LU` → SMARD | 1 Dec 2025 – 21 Aug 2026 |
| `data/raw/smard_public_power_de.csv` | `public_power?country=de` | same |
| `data/raw/smard_da_forecasts_de.csv` | `public_power_forecast` load/solar/wind | same |
| `data/processed/hourly_vpp_smard.csv` | resampled hourly, scaled | 6 319 h, 262 complete days, 403 negative hours |

Fetch script: `src/fetch_smard_expand.py`.  
Scale factors frozen: `sf_load=8.280e-5`, `sf_pv=6.890e-5`, `sf_w=4.810e-5`.

aFRR: published DE 4-hour block means (not a cleared tape) coded in `src/xu_pwl_model.py`.  
Imbalance: two-price function of DA in `src/gate10_core.py`.

Cited in the paper as [40] SMARD, [41] Energy-Charts, [42] Modo Energy, [43] Pexapark, [44] HiGHS.

---

## 2. Solvers and models (`src/`)

| Script | Role |
|---|---|
| `gate10_core.py` | SMARD ingest, block-bootstrap scenarios, throughput CVaR LP (B0/B2/P1), HiGHS |
| `relcca_model.py` | ReLCCA band LP + `fix_first_stage` / `evaluate_relcca_first_stage` |
| `xu_pwl_model.py` | Xu daily-depth PWL LP + aFRR block prices |
| `calibrate_kappa.py` | OLS Keil 25 °C plateaus → κ (NMC R²=0.89, LFP R²=0.92) |
| `run_multiseason.py` | Four isolation days, LFP map, r_max/E, winter+spring weeks |
| `run_soh_bootstrap.py` | Day-block bootstrap CIs; OLS-Keil May 1; linear SoH week |
| `run_regime_scan.py` | Nine extreme days; old-κ ablation; May-1 r_max/E; imb clip; wholesale decompose |
| `fetch_smard_expand.py` | Multi-season SMARD download |
| `regen_multiseason_figs.py` | Figs 1, 2, 5, 6, 7 |
| `html_to_docx_relcca.py` | HTML → Word |
| `ieee_style.py` | Plot style (no titles inside figures) |

Older pipeline (not in the new paper core): `run_relcca.py`, `run_relcca_g1g5.py`, `run_pipeline.py`, `run_extension_figures.py`.

---

## 3. Recorded result files

`Gate10_PAPER_EXTENSION/stats/`

| File | Content |
|---|---|
| `multiseason_results.csv` | 180 rows: isolation, LFP, r_max, E=2, winter/spring rolls |
| `regime_scan.csv` | 88 rows: 9 extreme days, old κ, May-1 sweeps, imb clip |
| `may1_decompose.csv` | DA / reserve / imb / DG / aging on 1 May |
| `may_ols_keil.csv` | 1 May with OLS-Keil κ |
| `soh_winter.csv` | Linear SoH roll 14–20 Jan |
| `bootstrap_ci.json` | 4000-resample CIs on weekly gaps |
| `kappa_ols.json` | Fitted κ and R² |

Frozen Gate-10 baseline (do not edit): `Gate10_REAL_RESULTS/` and `..._BASELINE_2026-08-21/`.

---

## 4. Figures in the paper (8)

| Fig. | File | What it shows |
|---|---|---|
| 1 | `Fig_MS_prices.png` | DA price on 20 Jan / 5 Apr / 1 May / 19 Aug |
| 2 | `Fig_MS_afrr.png` | Six aFRR 4-h blocks, up and down |
| 3 | `Fig_MS_litmap.png` | Literature-magnitude κ, γ_ch, γ_dis |
| 4 | `Fig_ReLCCA_cascade.png` | Eight-band cascade |
| 5 | `Fig_MS_gaps.png` | P1−B2 on four isolation days, three laws |
| 6 | `Fig_MS_rolls.png` | January and March–April P1 paths |
| 7 | `Fig_MS_rmax.png` | P1−B2 vs r_max on 19 Aug |
| 8 | `Fig_MS_depth.png` | P1−B2 vs daily min DA on nine extreme days |

Tables I–VI are in the HTML (laws, ratings, isolation, extreme scan, May-1 decompose, May-1 sensitivity).

---

## 5. Headline recorded numbers (all kOptimal unless noted)

**Isolation, K=30, aFRR blocks, NMC literature map**

| Day | Thr P1−B2 | Xu | ReLCCA |
|---|---:|---:|---:|
| 20 Jan | +930 | +926 | +1 212 |
| 5 Apr | +1 201 | +1 201 | +1 394 |
| **1 May** | **−246** | **−266** | **+515** |
| 19 Aug | +1 307 | +1 306 | +1 479 |

**Nine days with min DA < −50 (K=20):** throughput/Xu reverse **only 1 May**. 26 Apr still +139. Two ReLCCA-B2 rows not kOptimal (omitted). 24 May ReLCCA prefers energy-only (−1 783).

**Ablation 1 May, old κ 0.08–0.55:** ReLCCA **+513**.  
**OLS-Keil κ:** ReLCCA **+515**.  
**Imbalance |DA|≤150:** Thr −232, ReLCCA +541.  
**May r_max 0.5 / 2.5:** Thr −91 / −262; ReLCCA +234 / +800.

**Decompose 1 May wholesale:** B2-thr vs B2-ReLCCA gap 1 312 EUR, of which **1 246 is the DA energy bid**; aging 54 EUR.

**Bootstrap (7+7 days):** winter ReLCCA mean +1 463, CI [1 366, 1 531]; spring +1 396, [1 376, 1 415].

**SoH week:** 145 EUR aging → **0.019%** nameplate.

---

## 6. How to reproduce

```
python3 src/fetch_smard_expand.py    # optional; raw CSVs already stored
python3 src/calibrate_kappa.py
python3 src/run_multiseason.py
python3 src/run_soh_bootstrap.py
python3 src/run_regime_scan.py
python3 src/regen_multiseason_figs.py
python3 src/html_to_docx_relcca.py
```

Seed `20260821`. Solver HiGHS via `scipy.optimize.linprog(method="highs")`.

---

## 7. What was deliberately not claimed

No EV fleet. No cleared aFRR auction tape. No reBAP series. No Sandia/NASA raw-cell fit. No Shi rainflow extraction. No public GitHub URL from this sandbox. File `ReLCCA_VPP_EV_IEEE_Paper.html` is a pointer only.

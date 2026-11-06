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
Energy-Charts has **no** aFRR / reBAP endpoint. ENTSO-E returns 401 without a token.

Cited in the paper as [40] SMARD, [41] Energy-Charts, [42] Modo Energy, [43] Pexapark, [44] HiGHS.

---

## 2. Solvers and models (`src/`)

| Script | Role |
|---|---|
| `gate10_core.py` | SMARD ingest, block-bootstrap scenarios, throughput CVaR LP |
| `relcca_model.py` | ReLCCA band LP + `fix_first_stage`. Solver fallback: HiGHS simplex → presolve off → dual simplex → **IPM** |
| `xu_pwl_model.py` | Xu daily-depth PWL LP + aFRR block prices |
| `calibrate_kappa.py` | OLS Keil 25 °C plateaus → κ (NMC R²=0.89, LFP R²=0.92) |
| `run_multiseason.py` | Four isolation days, LFP map, r_max/E, winter+spring weeks |
| `run_soh_bootstrap.py` | Day-block bootstrap CIs; OLS-Keil May 1; linear SoH week |
| `run_regime_scan.py` | Nine extreme days (first pass; two Rel-B2 Status 0) |
| `run_review7_fixes.py` | Diagnose 24 May / 26 Apr / 2 May; solver recovery |
| `run_review7_rest.py` | Isolation on OLS-Keil; √t May 1; 24 May decompose; synthetic trough |
| `regen_review7_figs.py` | Figs 8, 9, 10 |
| `html_to_docx_relcca.py` | HTML → Word |

Do not edit: `Gate10_REAL_RESULTS/` and `Gate10_REAL_RESULTS_BASELINE_2026-08-21/`.

---

## 3. Recorded result files

`Gate10_PAPER_EXTENSION/stats/`

| File | Content |
|---|---|
| `multiseason_results.csv` | isolation / LFP / r_max / weeks (literature κ) |
| `regime_scan.csv` | first extreme scan (24 May Rel-B2 rec failed — **do not use that −1783**) |
| `review7_pairs.csv` | OLS-Keil isolation; √t May 1; recovered Xu |
| `review7_decompose.csv` | 1 May / 24 May wholesale (kOptimal) |
| `review7_recovered_b2.csv` | 26 Apr / 2 May Rel-B2 via HiGHS IPM |
| `review7_synth.csv` / `review7_synth_gaps.csv` | 19 Aug + scaled 1 May trough |
| `review7_logistic.json` | logistic of sign(P1−B2) on min DA (unidentified) |
| `may1_decompose.csv` | original 1 May decompose |
| `kappa_ols.json` | fitted κ and R² |
| `bootstrap_ci.json` | 4000-resample CIs |
| `soh_winter.csv` | linear SoH roll |

---

## 4. Figures in the paper (10)

| Fig. | File | What it shows |
|---|---|---|
| 1 | `Fig_MS_prices.png` | DA price on 20 Jan / 5 Apr / 1 May / 19 Aug |
| 2 | `Fig_MS_afrr.png` | Six aFRR 4-h blocks |
| 3 | `Fig_MS_litmap.png` | Literature-magnitude κ (ablation only) |
| 4 | `Fig_ReLCCA_cascade.png` | Eight-band cascade |
| 5 | `Fig_MS_gaps.png` | P1−B2 on four isolation days (Table III = OLS-Keil) |
| 6 | `Fig_MS_rolls.png` | January and March–April P1 paths |
| 7 | `Fig_MS_rmax.png` | P1−B2 vs r_max on 19 Aug |
| 8 | `Fig_MS_depth.png` | Nine extreme days, **all Rel rows kOptimal** |
| 9 | `Fig_MS_may24_da.png` | Energy-only DA bids, 1 May vs 24 May |
| 10 | `Fig_MS_synth.png` | Injected trough on 19 Aug: neither law crosses zero |

Tables I–VII in the HTML.

---

## 5. Headline recorded numbers (all kOptimal)

**Isolation, K=30, aFRR blocks, OLS-Keil NMC κ (Table III)**

| Day | Thr P1−B2 | Xu | ReLCCA |
|---|---:|---:|---:|
| 20 Jan | +930 | +926 | **+1 214** |
| 5 Apr | +1 201 | +1 201 | **+1 389** |
| **1 May** | **−246** | **−266** | **+515** |
| 19 Aug | +1 307 | +1 306 | **+1 480** |

**Nine extreme days (K=20), Rel recovered**

| Day | min DA | Thr | Rel |
|---|---:|---:|---:|
| 1 May | −499 | −246 | +531 |
| 26 Apr | −414 | +139 | **+869** (IPM; was —) |
| 2 May | −130 | +887 | **+1 188** (IPM; was —) |
| 24 May | −76 | +1 115 | **+1 316** (was −1 783, **withdrawn**) |

**24 May wholesale (Table VII):** B2-Rel DA −1 493, aging −35, WH −3 099; P1-Rel reserve +1 521, WH −1 783. Gap +1 316. Of the 439 B2-thr vs B2-Rel gap, 444 is the DA bid.

**√t annualisation (factor 0.913) on 1 May:** Rel **+516**.

**Synthetic trough on 19 Aug:** Thr P1−B2 = +1 145 … +790 from min −50 to −499. Never crosses. Rel always > +1 050.

**Logistic of sign on min DA:** 1 negative real observation (1 May throughput). Unidentified for ReLCCA. Not a threshold.

---

## 6. How to reproduce

```
python3 src/fetch_smard_expand.py    # optional; raw CSVs already stored
python3 src/calibrate_kappa.py
python3 src/run_multiseason.py
python3 src/run_soh_bootstrap.py
python3 src/run_regime_scan.py
python3 src/run_review7_fixes.py
python3 src/run_review7_rest.py
python3 src/regen_multiseason_figs.py
python3 src/regen_review7_figs.py
python3 src/html_to_docx_relcca.py
```

Seed `20260821`. Solver HiGHS via `scipy.optimize.linprog`. Rel-B2 on 26 Apr / 2 May needs the IPM fallback in `relcca_model._LP.solve`.

---

## 7. What was deliberately not claimed

No EV fleet. No cleared aFRR auction tape. No reBAP series. No Sandia/NASA raw-cell fit. No Shi rainflow extraction. No public GitHub URL from this sandbox. File `ReLCCA_VPP_EV_IEEE_Paper.html` is a pointer only. The −1 783 EUR 24 May ReLCCA ranking is **not** a result.

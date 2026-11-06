# Final IEEE paper package — Gate 10

## Paper (open these)

- `Hassanli_Abbasi_VPP_Bidding_IEEE.docx` — IEEE-style manuscript with real figures (no internal titles) and filled tables
- `Hassanli_Abbasi_VPP_Bidding_IEEE.html` — same content, two-column HTML

Figures used in the paper live in `figures/` (PNG 300 dpi + PDF). Captions are **below** the graphics, not inside them.

## Code (what was actually run)

`code/`
- `gate10_core.py` — SMARD ingest, block-bootstrap scenarios, HiGHS LPs (B0, B2, P1)
- `run_pipeline.py` — baseline freeze, Phases A–D, sensitivity, stats, IEEE tables
- `ieee_style.py` — journal plotting style
- `regen_untitled_figures.py` — regenerate figures without internal titles
- `build_ieee_paper.py` — this manuscript

## Results

`results/Gate10_REAL_RESULTS/` — frozen operating-day CSVs/XLSX/JSON  
`results/paper_extension/` — sensitivity, rolling OOS, statistical tests, Tables I–VI  
`results/data/` — raw SMARD extracts and hourly VPP panel

The bit-identical freeze of the baseline (do not edit) is also at  
`/home/user/Gate10_REAL_RESULTS_BASELINE_2026-08-21/`

## Headline numbers (19 Aug 2026, SMARD DE-LU)

| Model | E[profit] | CVaR0.95 | Realized | HiGHS |
|---|---:|---:|---:|---|
| B0 | 11 497.86 | 9 985.66 | 10 938.36 | kOptimal |
| B2 | 11 508.28 | 10 026.78 | 10 964.67 | kOptimal |
| P1 | 11 991.79 | 10 440.13 | 11 486.96 | kOptimal |

P1 − B0: +494 EUR/day in sample (d = 6.29); +563 EUR/day over 14 OOS days.

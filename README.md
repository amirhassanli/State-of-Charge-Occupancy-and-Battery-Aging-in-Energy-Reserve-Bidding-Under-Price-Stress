# SoC-Occupancy Aging and Energy–Reserve Bidding

This repository contains a reviewer-facing **reconstruction and diagnostic package** for the manuscript *SoC-Occupancy Aging in a Battery Energy Storage System: Energy–Reserve Bidding under Stressed Prices*. It is not the original study implementation and does not reproduce the manuscript's reported numerical tables. The original Pyomo/HiGHS source and exact original run configuration were not supplied.

## Canonical project files

| Purpose | Canonical location |
|---|---|
| Current production manuscript | [`SoC_Occupancy_Aging_Energy_Reserve_Bidding_FINAL_SUBMISSION.docx`](./SoC_Occupancy_Aging_Energy_Reserve_Bidding_FINAL_SUBMISSION.docx) |
| Markdown reading copy | [`paper/FINAL_SUBMISSION.md`](./paper/FINAL_SUBMISSION.md) |
| Reconstruction model and diagnostics | [`code/agingbid/`](./code/agingbid/) and [`code/run_diagnostics.py`](./code/run_diagnostics.py) |
| Market/system input panel | [`data/processed/hourly_vpp_panel_2025-12-01_2026-08-21.csv`](./data/processed/hourly_vpp_panel_2025-12-01_2026-08-21.csv) |
| Archived reconstruction outputs | [`data/results/`](./data/results/) |
| Data and parameter provenance | [`data/README.md`](./data/README.md), [`data/parameters/battery_model.json`](./data/parameters/battery_model.json), and [`data/metadata/`](./data/metadata/) |

`paper/` contains reviewed/revised working documents and the Markdown reading copy. `Hassanli_Abbasi_Occupancy_Aging_IEEE-v8.docx` and other versioned Word files are retained for comparison; they are not the canonical production manuscript. `arena/` and `agingbid_review/` contain historical/reference material, not execution entry points.

## What the repository can and cannot establish

- The model in `code/agingbid/` is implemented with `scipy.optimize.milp` and SciPy's HiGHS backend. It is an independent reconstruction from the manuscript equations, not the manuscript's original Pyomo implementation.
- Results under `data/results/` are reconstructed diagnostics. Do not substitute them for the manuscript's original Tables III–VI or describe them as an exact reproduction.
- The E4 crossed settlement/optimization experiment is in `code/e_tests/results/E04_settlement_2x2.csv`. Its relaxed-LP “reBAP-optimised” case uses the realized same-day reBAP as an optimization input (perfect foresight, labelled LEAKY); it is not an ex-ante result or a settlement-only effect.
- The archived panel contains 6,319 hourly rows and 262 complete days, from 1 December 2025 through 21 August 2026. Load, PV, and wind are public national series scaled to the study portfolio; they are not measurements from a particular VPP or battery.
- Reserve prices use four-hour block values, and the default imbalance settlement is a deterministic proxy, not observed reBAP. Some separate sensitivity results use real reBAP; they do not make the default model a real-market settlement model.
- No battery telemetry, cell chemistry/temperature history, or measured state-of-charge/degradation series is included. Battery aging outputs are model-based and are not empirical validation of a physical battery.
- Input and parameter provenance is separated in `data/parameters/battery_model.json`: manuscript-reported values, quantities not reported in the manuscript, and reconstruction-only defaults. Reconstruction defaults are not evidence of the original authors' settings.

These limitations are intrinsic to the currently available source material. They can only be removed by obtaining the original implementation/configuration and appropriate battery measurements, not by relabeling the reconstruction.

## Environment and reproducibility

GitHub Actions is configured to test Python 3.12–3.14. Direct dependencies are pinned in [`requirements.txt`](./requirements.txt); transitive packages are resolved by pip, and `code/requirements.txt` includes the same root dependency list.

From the repository root:

```bash
python -m pip install -r requirements.txt
cd code
python -m pytest tests -q
python validate_artifacts.py
```

The tests use synthetic data for model smoke checks. Artifact validation separately checks the archived panel and raw-data hashes, row/day counts, diagnostic outputs, parameter declarations, VS Code task configuration, and the manuscript disclosures.

To regenerate a diagnostic without overwriting the archived outputs, run from `code/`:

```bash
python run_diagnostics.py --panel ..\data\processed\hourly_vpp_panel_2025-12-01_2026-08-21.csv --mode cross --day 2026-05-01 --K 30 --seed 20260821 --exclusive --out ..\data\results\reproduced_milp
```

The `--exclusive` option imposes binary charge/discharge exclusivity. Without it, the LP relaxation can charge and discharge simultaneously; consult the overlap diagnostics before interpreting relaxed-LP results. See [`code/README.md`](./code/README.md) and [`data/results/README.md`](./data/results/README.md) for commands, settings, and output interpretations.

## Data availability and licenses

Code, archived inputs, and reconstruction outputs are available in this GitHub repository: <https://github.com/amirhassanli/State-of-Charge-Occupancy-and-Battery-Aging-in-Energy-Reserve-Bidding-Under-Price-Stress>. No archival DOI has been minted for this repository; cite a versioned release or commit and do not imply that a DOI exists. Source URLs, retrieval details, provider licenses, and checksums are recorded under `data/metadata/`. Recheck the relevant provider terms before redistributing source data. Earlier project documentation describes the code as MIT-licensed, but this repository currently has no root license text; the repository owner should add the approved license file before treating that declaration as formal.

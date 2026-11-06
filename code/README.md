# agingbid_review

Reviewer-facing reconstruction of the daily mean–CVaR energy–reserve model with three aging laws
(throughput, daily DoD, and ReLCCA). The original manuscript implementation was not supplied, so this
package is not an exact reproduction of the published runs. Code-only assumptions are identified in
`agingbid/core.py` and `../data/parameters/battery_model.json`.

| mode | what it answers |
|---|---|
| `cross` | 3×3 cross-evaluation (bid made under law i, settled under law j); DA-window position; **simultaneous charge/discharge** overlap; **ε-optimal range** of the DA position (near-tie / degeneracy test) |
| `seeds` | how often the sign of P1−B2 flips when only the K-scenario draw changes (Clopper–Pearson CI) |
| `scan`  | all negative-price (or `--all_days`) days: reversal counts with Wilson / Clopper–Pearson CIs, paired block-bootstrap + Wilcoxon |
| `beta`  | sensitivity to the CVaR weight β |

`--exclusive` adds binary charge/discharge exclusivity (MILP). Without it, the LP relaxation can
simultaneously charge and discharge; inspect the `overlap_MWh` diagnostic before interpreting results.

## Data and Reproduction

From this directory, download and archive the official historical panel:

```powershell
python download_market_data.py
```

Then run the tests and a 1 May cross-evaluation:

```powershell
python -m pytest tests -q
python run_diagnostics.py --panel ..\data\processed\hourly_vpp_panel_2025-12-01_2026-08-21.csv --mode cross --day 2026-05-01 --K 30 --seed 20260821 --exclusive --out ..\data\results\exclusive_milp
```

The panel contains DE-LU day-ahead prices from Bundesnetzagentur | SMARD.de and German load, solar, and
wind series from Fraunhofer ISE Energy-Charts. Source URLs, retrieval date, licenses, series, and hashes
are recorded in `../data/metadata/`. National physical series are rescaled to the study portfolio.
This is not battery telemetry: battery size, efficiencies, and aging costs are model parameters.

The code uses SciPy's MILP interface. The manuscript's original Pyomo/HiGHS source and exact original
input/configuration are still needed to reproduce its reported numerical tables. The current reruns are
archived separately under `../data/results/` and are not substitutes for those tables.

The panel CSV columns expected by the model are `timestamp, da_price, load, pv, wind` (MW-scaled load,
PV, and wind); optional `load_fc, pv_fc, wind_fc` can provide forecasts. Without forecast columns,
48-hour persistence is used. Scenario errors are drawn only from days no later than D−2.
`synthetic.py` is for smoke tests only; no result from it may be reported as empirical.

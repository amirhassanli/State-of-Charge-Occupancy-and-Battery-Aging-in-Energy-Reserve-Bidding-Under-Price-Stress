# agingbid_review — reviewer-facing diagnostics

Re-implementation (from the manuscript equations) of the daily mean–CVaR energy–reserve LP with three
aging laws (thr / xu / relcca) + diagnostics that a referee is likely to ask for:

| mode | what it answers |
|---|---|
| `cross` | 3×3 cross-evaluation (bid made under law i, settled under law j); DA-window position; **simultaneous charge/discharge** overlap; **ε-optimal range** of the DA position (near-tie / degeneracy test) |
| `seeds` | how often the sign of P1−B2 flips when only the K-scenario draw changes (Clopper–Pearson CI) |
| `scan`  | all negative-price (or `--all_days`) days: reversal counts with Wilson / Clopper–Pearson CIs, paired block-bootstrap + Wilcoxon |
| `beta`  | sensitivity to the CVaR weight β |

`--exclusive` adds binary charge/discharge exclusivity (MILP).

Panel CSV columns: `timestamp, da_price, load, pv, wind` (already scaled to plant MW), optional `load_fc, pv_fc, wind_fc`
(map names with `--cols '{"price":"..."}'`). Scenario errors use days ≤ D−2 only.

**Placeholders to replace with your published values** (flagged `# ASSUMPTION` in core.py): `tau`, `gamma_*`, `E0`, grid limit, curtailment treatment.
`synthetic.py` is for smoke tests only; no number from it may be reported.

# German Market Scope and Real-Source Acquisition Plan

## 1. Recommended final scope

To preserve real-data integrity and avoid a paper built on assumed intraday spreads or reserve prices, the study should be implemented in two tiers.

### Tier 1 — Mandatory, fully real empirical core

**Day-ahead bidding plus balancing-group imbalance settlement in DE-LU.**

This tier requires only data whose real observations and settlement definitions can be obtained and audited:

- DE-LU signed day-ahead clearing prices;
- actual German PV, onshore wind, offshore wind, and load;
- decision-eligible forecasts or leakage-free reconstructed forecast vintages;
- native reBAP balancing prices and actual portfolio/system deviations;
- real BESS/DG/DR asset data, or a transparently representative portfolio;
- German holiday/calendar information.

Tier 1 is sufficient to demonstrate the paper’s main novelty: negative-price regime-conditioned uncertainty, signed-price recourse, imbalance exposure, and a real common-calendar OOS evaluation.

### Tier 2 — Conditional ancillary-service extension

Add reserve capacity and activation only if all of the following are available before modeling:

- product-specific capacity prices;
- product-specific activation prices/volumes;
- gate closure and product-duration rules;
- minimum bid requirements;
- actual reserve qualification/availability of modeled assets;
- exact settlement logic.

If any item is unavailable, reserve-market revenue must not be represented through a fabricated generic price. The paper retains **energy-aware N−1 flexibility** as an internal physical security metric, but does not claim participation in a specific reserve market. This is more defensible than preserving a broader scope with assumed inputs.

### Tier 3 — Conditional intraday extension

Add intraday trading only with real time-stamped intraday prices and verified gate/product conventions. Do not use `DA price ± arbitrary spread` in the final study. If Tier 3 is not executed, state clearly that recourse occurs through physical balancing/imbalance settlement rather than intraday trading.

## 2. Why this scope improves acceptance probability

A narrower model with real DA and reBAP settlement is stronger than a multi-market model containing assumed ID spreads, generic reserve prices, or proxy activation revenues. It gives the paper a clean central claim:

> The proposed framework improves the representation and management of joint renewable, load, and price uncertainty in German day-ahead bidding when real negative prices and balancing-group imbalance settlement are retained.

The ancillary-service version remains a documented extension, not an unsupported core assumption.

## 3. Real-source acquisition register

The register below must be completed before download. Every source is saved with URL, retrieval timestamp, native frequency, unit, geographic zone, license, and SHA-256 after download.

| Dataset | Study role | Preferred real source | Required frequency | Mandatory fields | Go/no-go check |
|---|---|---|---:|---|---|
| DE-LU DA price | Decision and negative-price regime | SMARD / Bundesnetzagentur market data | Hourly or market-native | delivery timestamp, signed clearing price | Full 2024/2025 coverage, negative values retained |
| Actual PV | Physical settlement | SMARD | 15-min or hourly | timestamp, MW, source definition | Same definition throughout both years |
| Actual onshore wind | Physical settlement | SMARD | 15-min or hourly | timestamp, MW | Same definition throughout both years |
| Actual offshore wind | Physical settlement | SMARD | 15-min or hourly | timestamp, MW | Same definition throughout both years |
| Actual load | Physical settlement | SMARD | 15-min or hourly | timestamp, MW, load definition | No forecast/actual definition mismatch |
| Renewable/load forecasts | Pre-decision inputs | Official forecast-vintage source or reproducible historical forecast pipeline | Gate-specific hourly | issued time, delivery time, forecast | Eligibility proof required |
| Price forecast | Pre-decision input | Official forecast vintage or reproducible historical forecast pipeline | Gate-specific hourly | issued time, delivery time, forecast | Cannot use realized DA price |
| reBAP | Imbalance settlement | Netztransparenz / German TSO publication | 15-min | timestamp, signed reBAP, relevant metadata | Contract sign mapping confirmed |
| Reserve data | Tier 2 only | Official TSO/market publication | Product-specific | price, volume, gate, duration | All product rules available |
| Intraday data | Tier 3 only | Auditable licensed/official source | Product-specific | timestamped trades/index | No proxy spread allowed |
| Holidays | Calendar covariate | Official German calendar source | Daily | date, region, holiday name | Version recorded |

## 4. Forecast acquisition decision

Realized system observations alone are not valid decision-time forecasts. The project selects one of the following before modeling.

### Route F1 — Published real forecast vintages

Use a source with documented forecast issuance and delivery times for price, load, PV, and wind. This is strongest, but availability must be verified for the selected 2024–2025 coverage.

### Route F2 — Leakage-free reconstructed forecasts

When publicly archived vintages are not available, produce forecasts through a fully reproducible rolling procedure. At each historical gate, train only on prior observations and features available by that gate; save the model version, training cutoff, features, forecast, and issuance time. These are not “observed published forecasts,” but they are valid historical decision-time forecasts if the information set is rigorously reconstructed.

Route F2 is acceptable for peer review only if it is described transparently and the exact code/data lineage is released. It must never use actual future values or a forecast model tuned on the frozen 2025 OOS results.

## 5. Required source-level metadata

For every download create a row in `raw_manifest_YYYY.csv`:

```text
source_dataset_id,description,official_url,retrieved_at_utc,coverage_start_utc,
coverage_end_utc,zone,native_frequency,unit,timezone_as_published,license,
original_filename,local_filename,row_count,sha256,known_revision_note
```

For every source-to-canonical transformation create a record:

```text
input_sha256,output_filename,output_sha256,transform_version,aggregation_rule,
timezone_rule,unit_conversion,missing_value_rule,operator,executed_at_utc
```

## 6. Acquisition order

1. Finalize Tier 1 scope and lock it in `experiment_locked.yaml`.
2. Download all 2024 and 2025 DA price, physical actual, and reBAP raw files.
3. Validate coverage, units, signs, and timezone before combining anything.
4. Resolve the forecast route F1 or F2.
5. Obtain/lock real asset data and contract information, or define the transparent representative-portfolio wording.
6. Decide whether Tier 2 reserve and Tier 3 intraday pass their real-data go/no-go tests.
7. Only then build canonical panels and begin forecast/scenario/model coding.

## 7. Scope-language templates

### If only Tier 1 passes

> “The empirical study considers a renewable-based VPP participating in the German/Luxembourg day-ahead market and exposed to real balancing-group imbalance settlement. The framework evaluates physical flexibility and energy-aware N−1 deliverability; it does not claim revenue from an ancillary-service product whose full public settlement inputs were unavailable.”

### If Tier 1 and Tier 2 pass

> “The empirical study co-optimizes day-ahead bidding and [exact reserve product] participation using product-specific published prices, gate rules, activation requirements, and settlement conventions.”

### If Tier 3 passes as well

> “Intraday recourse is modeled using time-stamped [exact product] prices and the documented market-gate chronology.”

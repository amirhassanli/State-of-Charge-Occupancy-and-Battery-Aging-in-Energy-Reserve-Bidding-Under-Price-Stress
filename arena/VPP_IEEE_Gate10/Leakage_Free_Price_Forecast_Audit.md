# Leakage-Free Historical Day-Ahead Price Forecast — Initial Audit

## Objective

A realized day-ahead clearing price cannot be used as the historical day-ahead forecast. To establish a real, reproducible, leakage-free price input before a richer forecast model is selected, a conservative rolling baseline was constructed from the official sorted SMARD DE-LU day-ahead price history.

## Forecast F2-baseline-v1

For every delivery date \(D\) and Berlin delivery hour \(h\), the baseline forecast is the median of the eight most recent historical observations with the same Berlin weekday and hour. To make the information rule deliberately conservative, training data are restricted to market dates no later than \(D-2\):

\[
\widehat\lambda_{D,h}=\operatorname{median}\left\{\lambda_{d,h}:d\le D-2,\;\operatorname{weekday}(d)=\operatorname{weekday}(D)\right\}.\tag{1}
\]

If fewer than four same-weekday observations are available, the model falls back to the most recent 56 observations at the same Berlin hour; if fewer than four observations remain, it returns missing rather than using future data. The forecast record is assigned an issue time of 10:00 Europe/Berlin on \(D-1\). Since all training observations end at \(D-2\), this protocol is stricter than necessary and cannot use the price realized on the delivery day or immediately preceding market day.

## Real 2025 diagnostic

| Metric | Result |
|---|---:|
| 2025 delivery hours forecasted | 8,760 |
| MAE | 27.6883 €/MWh |
| Bias | 1.8460 €/MWh |
| RMSE | 41.7766 €/MWh |
| Actual negative-price hours | 576 |
| Negative-price forecast hours | 393 |
| Forecast issued after delivery | 0 |

The baseline is not intended to be the final accuracy-maximizing forecaster. Its role is to prove a fully traceable leakage-free price-forecast route and establish a benchmark for later pre-registered forecast improvements. In particular, its lower count of negative predicted hours compared with observed negative hours makes regime calibration and tail-aware scenario construction practically relevant.

## Artifacts

```text
canonical/da_price_forecast_F2_leakage_free_2024_2025.parquet
canonical/da_price_forecast_F2_leakage_free_2024_2025.csv
canonical/da_price_forecast_F2_initial_diagnostics_2025.csv
build_leakage_free_price_forecast.py
```

Each forecast row stores `timestamp_utc`, Berlin delivery date, `issued_at_utc`, training cutoff date, forecast model ID, forecast value, and number of historical observations. This gives the future OOS runner an auditable information-set record.

## Scope limitation

This price forecast does not make the SMARD renewable/load forecast-candidate series automatically decision-eligible. Their publication timing remains under audit. Until that timing is verified, they are used only for descriptive residual analysis, not for final bid submission. A leakage-free rolling reconstruction can be used for all uncertain series if official forecast-vintage issue times cannot be verified.

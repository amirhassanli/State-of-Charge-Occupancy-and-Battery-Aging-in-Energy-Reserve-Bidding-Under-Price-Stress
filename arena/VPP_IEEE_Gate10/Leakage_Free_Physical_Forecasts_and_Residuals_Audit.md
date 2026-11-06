# Leakage-Free Physical Forecasts and Real Residual Panel — Initial Audit

## 1. Conservative forecast construction

Leakage-free F2 baseline forecasts were constructed for PV, onshore wind, offshore wind, and load using the same conservative historical information rule used for day-ahead price: for delivery date \(D\), forecast inputs end at \(D-2\). Each forecast is a same-Berlin-weekday/same-Berlin-hour historical median, with a same-hour fallback. Every 2025 record has a stored issue time, training cutoff, and zero cases in which `issued_at_utc >= delivery_start_utc`.

The resulting source-backed artifacts are:

```text
canonical/physical_forecasts_F2_leakage_free_2024_2025.parquet
canonical/physical_forecasts_F2_leakage_free_2024_2025.csv
canonical/physical_forecasts_F2_initial_diagnostics_2025.csv
canonical/real_residual_panel_F2_2024_2025.parquet
canonical/real_residual_summary_F2_2025.csv
canonical/real_residual_correlation_F2_2025.csv
canonical/real_residual_acf_F2_2025.csv
```

## 2. Initial real 2025 forecast diagnostics

| Series | MAE (MW) | Bias (MW) | RMSE (MW) | Forecast after delivery |
|---|---:|---:|---:|---:|
| PV | 793.17 | −71.28 | 1,501.45 | 0 |
| Onshore wind | 1,875.63 | −306.63 | 2,481.84 | 0 |
| Offshore wind | 448.90 | −55.83 | 547.44 | 0 |
| Load | 576.10 | 8.62 | 804.37 | 0 |

These are conservative, transparent baseline forecasts, not the final forecasting layer. Their principal role is to make the historical information set explicit and to produce a valid real residual panel before improving forecast accuracy with a pre-registered rolling forecast model.

## 3. Why temporal modeling is required

The real residual panel shows very high short-lag autocorrelation. For example, the lag-1 ACF is approximately 0.985 for load residuals and 0.991 for onshore-wind residuals under this conservative baseline. Significant persistence remains over daily and weekly lags. Therefore, independently sampling every hour from a marginal or cross-sectional copula would be methodologically invalid for this application.

The real residual correlation matrix also shows cross-variable structure. The full matrix is stored in `real_residual_correlation_F2_2025.csv`; the model must preserve this structure jointly with temporal persistence. This provides empirical support for the temporal-filter-plus-regime-conditioned-copula architecture proposed for ChronosBid.

## 4. Interpretation boundary

The current baseline forecast errors include both unpredictable uncertainty and predictable structure left by a deliberately simple, conservative forecaster. They must not be presented as the final forecast-performance result. The final scenario engine will be fitted using residuals from a selected rolling forecaster, chosen only on the 2024 warm-up/validation period. The 2025 frozen OOS period will evaluate that locked design.

## 5. Immediate next modeling step

Select the final pre-gate rolling forecasters for price, PV, wind, and load on 2024 data only. Candidate models may include seasonal-naïve, regularized autoregression with calendar features, and other fully reproducible specifications. The selection criterion must combine forecast accuracy and calibration quality, be locked before the 2025 OOS run, and retain the full forecast-vintage audit trail.

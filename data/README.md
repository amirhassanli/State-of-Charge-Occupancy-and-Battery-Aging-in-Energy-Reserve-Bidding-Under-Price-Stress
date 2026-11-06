# Study Data Package

## Categories

- `raw/energy_charts/`: unchanged JSON responses retrieved from the Energy-Charts API. Includes DE-LU day-ahead prices (licensed by Bundesnetzagentur | SMARD.de) and German public power data.
- `processed/`: local-time hourly panel derived from the archived API responses. Load is scaled so its study-period 95th percentile is 5 MW; solar maximum is mapped to 4 MW; combined onshore/offshore wind maximum is mapped to 2 MW. These are portfolio scaling operations, not battery measurements.
- `metadata/`: retrieval time, source URLs, licenses, series names, units, hashes, date coverage, and scaling factors.
- `parameters/battery_model.json`: battery design and aging settings separated into manuscript-reported values and code-only assumptions.

## Important Scope Note

This package contains no measured battery telemetry, cell test data, temperature series, or field-BESS state-of-charge history. The 2.5 MW / 5 MWh battery, efficiencies, SoC bounds, and aging costs are model parameters. The paper's calendar-aging kappa plateaus are literature-based economic inputs; the reconstruction's cycle-aging gamma coefficients, initial SoC, and reserve-sustainment duration are code assumptions. None of these is a downloaded battery dataset. The public time series are market prices and national grid/load/generation data.

## Rebuild

From the `code` directory, run:

```powershell
python download_market_data.py
```

The script archives the original responses before creating the processed panel. The requested source interval is 2025-12-01 through 2026-08-21; processed observations stop at 07:00 Berlin time on the final date to match the manuscript's stated cutoff. All times are converted to `Europe/Berlin`; 15-minute API values are averaged to hourly values. Missing raw values are not imputed.

The public API documents CC BY 4.0 attribution and endpoint-specific licensing. Cite Bundesnetzagentur | SMARD.de for price data and Fraunhofer ISE Energy-Charts for public power data. Keep the generated manifest with any redistributed processed dataset.

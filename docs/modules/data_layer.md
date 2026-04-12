# Data Layer

## Overview
The data layer stores raw market data in SQLite and exposes normalized read/write helpers that are reused by
the trend feature store.

## Databases
- `data/daily.db`
  Raw daily OHLCV bars in `daily_bars`
- `data/intraday.db`
  Raw intraday OHLCV bars in `intraday_bars`
- `data/feature.db`
  Derived daily trend features in `trend_features_daily`

## Runtime Config
`app/runtime/config_loader.py` resolves these paths from the `data` section:
- `daily_db_path`
- `intraday_db_path`
- `feature_db_path`
- `symbols_db_path`
- `account_db_path`
- `logs_db_path`

## Shared Helpers
- `app.data.repository.save_bars(...)`
- `app.data.repository.load_bars(...)`
- `app.data.updater.update_symbol_data(...)`
- `app.trend.features.init_feature_db(...)`
- `app.trend.features.update_feature_db(...)`

## Daily To Feature Dependency
`feature.db` depends on `daily.db`.
Feature generation always reads actual trade dates from `daily_bars`, computes `hist_*` / `fut_*` features on top
of those rows, and upserts the result into `trend_features_daily`.

When history is insufficient for a requested feature update window, the feature module refreshes `daily.db` through
`YFinanceProvider` before recomputing the affected rows.

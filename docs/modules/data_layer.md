# Data Layer

## Overview
The data layer stores raw market data in SQLite and exposes normalized read/write helpers that are reused by
the trend feature store.

## Databases
- `data/daily.db`
  Raw daily OHLCV bars in `daily_bars`, plus date-level coverage state in `daily_coverage`
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
- `app.data.updater.update_daily_db(...)`
- `app.trend.features.init_feature_db(...)`
- `app.trend.features.update_feature_db(...)`
- `app.trend.features.load_feature_rows(...)`

## Daily To Feature Dependency
`feature.db` depends on `daily.db`.
Feature generation always reads actual trade dates from `daily_bars`, computes `hist_*` / `fut_*` features on top
of those rows, and upserts the result into `trend_features_daily`.

## Daily Coverage
`daily.db` now uses two tables for daily maintenance:
- `daily_bars`
  Stores only valid OHLCV rows.
- `daily_coverage`
  Stores per-date coverage state for each ticker and interval so missing calendar dates do not need to be
  re-checked from scratch on every update.

`update_daily_db(...)` is the only supported write entry point for `daily.db`.
It checks coverage gaps, fetches only unchecked weekday segments through the provider interface, saves valid bars,
and records coverage status for every checked calendar date.

## Feature Cache Semantics
`update_feature_db(...)` is the only supported write entry point for `feature.db`.
It first calls `update_daily_db(...)`, then computes only the missing feature trade dates inside the requested range.

Already cached feature rows are reused by default.
The only existing feature rows that are recomputed are the small left-boundary windows needed to mature nearby
`fut_*` columns after new right-side data appears.

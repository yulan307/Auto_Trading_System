# Trend Feature Store

## Overview
`app/trend/features.py` is the shared trend-feature module for daily research and future strategy analysis.
It computes the full `hist_*` / `fut_*` feature set defined in `docs/research/trend_feature_script_spec_codex.md`
and persists reusable rows into `data/feature.db`.

## Storage
- Database: `data/feature.db`
- Table: `trend_features_daily`
- Primary key: `(ticker, datetime)`
- Base columns: `ticker`, `datetime`, `interval`, `open`, `high`, `low`, `close`, `volume`, `source`, `update_time`
- Derived columns: all `hist_*`, `fut_*`, `*_drv2_*`, `*_drv5_*`, and `*_pct_*`

`interval` is currently fixed to `1d`.

## Public Entry Points
- `init_feature_db(...)`
  Creates `feature.db` and `trend_features_daily` when missing, and adds any missing columns on existing tables.
- `update_feature_db(ticker, start_date, end_date, ...)`
  Updates the feature store for one ticker and date range, then returns `True` on success.
- `run_trend_feature_pipeline(...)`
  Shared batch helper used by the CLI wrapper in `scripts/compute_trend_features.py`.

## Update Flow
1. Read daily bars for `ticker` from `data/daily.db`.
2. Read existing feature rows from `data/feature.db`.
3. Identify missing feature dates from actual `daily_bars` trade dates only.
4. Split missing dates into contiguous trade-date segments.
5. For each segment, also include the prior 9 trade dates as a backfill window so recently matured `fut_*` rows can be recomputed.
6. Compute a warmup fetch window using:
   - `hist` warmup requirement
   - plus the `pct` history requirement
7. If daily data is insufficient for the segment window, refresh daily bars through `YFinanceProvider`.
8. Recompute features on the full warmup window and upsert the target rows into `trend_features_daily`.

## Warmup Rules
- `hist` warmup bars: `239`
- `pct` history bars: `256`
- total warmup bars before the target row: `495`
- if history is still genuinely unavailable after fetching, feature columns remain `NaN`

## Notes
- Old MA-only trend classification is deprecated and no longer the source of truth for strategy analysis.
- New analysis work should read `hist_*` columns from `feature.db`.

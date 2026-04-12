# Trend Feature Store

## Overview
`app/trend/features.py` is the shared trend-feature module for daily research and future strategy analysis.
It computes the full `hist_*` / `fut_*` feature set defined in `docs/research/trend_feature_script_spec_codex.md`
and persists reusable rows into `data/feature.db`.
`feature.db` is now the only maintained trend-feature store.

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
- `load_feature_rows(...)`
  Reads cached feature rows back from `trend_features_daily`.
- `run_trend_feature_pipeline(...)`
  Batch helper used by `scripts/compute_trend_features.py`. It now updates `data/feature.db` first and then exports
  CSVs by reading from that same cache.

## Update Flow
1. Call `update_daily_db(...)` for the warmup-plus-request window.
2. Read actual trade dates from `daily_bars`.
3. Read existing feature dates from `trend_features_daily`.
4. Identify only the missing feature trade-date segments inside the requested range.
5. For each missing segment, include up to 9 existing trade dates on the left so nearby `fut_*` values can mature.
6. Compute features from `daily.db` only, using the required warmup bars plus any locally cached right-side future bars.
7. Upsert only:
   - the newly missing dates
   - the existing left-boundary rows that need `fut_*` backfill

Existing feature rows outside those left-boundary backfill windows are reused as cache entries and are not recomputed.

## Warmup Rules
- `hist` warmup bars: `239`
- `pct` history bars: `256`
- total warmup bars before the target row: `495`
- if history is still genuinely unavailable after fetching, feature columns remain `NaN`

## Notes
- `feature.db` is treated as a reusable cache, not a repair-oriented history rewrite store.
- Old MA-only trend classification is deprecated and no longer the source of truth for strategy analysis.
- New analysis work should read `hist_*` columns from `feature.db`.

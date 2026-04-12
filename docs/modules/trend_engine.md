# Trend Engine

## Current Direction
The trend module no longer uses the old MA-order plus slope-code classification chain as the primary analysis path.
Trend analysis is now based on the reusable feature store in `app/trend/features.py`.

## Source Of Truth
- raw bars: `data/daily.db`
- derived features: `data/feature.db`
- primary inputs for future strategy work: `hist_*` columns

## Status
- old `compute_ma_features(...)` flow: removed
- old `classify_trend(...)` flow: removed
- feature-store flow: active

## Recommended Usage
1. Ensure daily bars exist in `data/daily.db`
2. Call `update_feature_db(...)`
3. Read `hist_*` rows from `trend_features_daily`
4. Build strategy or research logic on top of those features

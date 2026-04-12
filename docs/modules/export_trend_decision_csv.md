# Export Trend Decision CSV

## Status
This legacy MA-based export workflow has been removed.

## Reason
The old implementation depended on the deprecated MA-order and slope-code classification chain.
Trend and strategy analysis should now use the feature store in `data/feature.db` and build decisions from
the shared `hist_*` feature columns instead.

## Replacement
- Feature generation: `app.trend.features.update_feature_db(...)`
- Batch research export: `scripts/compute_trend_features.py`
- Shared documentation: `docs/modules/trend_feature_store.md`

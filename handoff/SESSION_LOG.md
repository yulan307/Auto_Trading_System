# Session Log

## 2026-04-14

### Codex

- Created the shared `handoff/` area for Claude/Codex relay work
- Linked the workflow from `CLAUDE.md`
- Pre-filled the current known blocker from repository guidance: missing trend entry points used by the backtest loop
- Added `CODEX.md` so night sessions have a repo-local operating guide aligned with the same handoff workflow

### Claude (session 1)

- Verified Phase 1 was fully closed: `app/trend/features.py` and `app/trend/classifier.py` were implemented
- Confirmed the backtest blocker was resolved and tests were passing at that point
- Updated handoff files to remove the stale blocker and point toward Phase 2

### Claude (session 2)

- Trained and promoted `buy/v001`
- Ran inference and verified CSV output includes `pred_strength_pct`
- Confirmed `buy_strength.db` label generation was populated
- Updated project guidance and current development notes

### Claude (session 3)

- Expanded training and feature validation around the updated percentile / warmup semantics
- Fixed the feature percentile design to use a calendar-based history window
- Updated trend feature scripts and tests to match the new warmup logic

### Claude (session 4)

- Rebuilt `feature.db` and retrained `buy/v001`
- Re-checked GOOGL inference coverage and NaN gaps
- Confirmed model artifacts and registry state on 2026-04-14

### Claude (session 5)

- Worked on branch `feature/closed-loop-backtest`
- Fixed JSON serialization for trend decision output
- Fixed backtest account reset / cash deduction issues
- Added sell-side closed-loop behavior and metrics support
- Left the closed-loop backtest branch ready for PR / merge

## 2026-04-15

### Codex

- Worked on branch `feature/ml-signal-integration`
- Re-read `docs/ml_integration_focus.drawio` and aligned implementation to the updated intent:
  `buy_activate_price` is the chosen name
- Confirmed `app/ml/buy_sub_ml/` already contains full dataset / trainer / registry / inference code
- Added runtime single-ticker inference helper:
  `app.ml.buy_sub_ml.inference.infer_buy_strength_signal_inputs()`
- Runtime inference now:
  - reads `ml.buy_model_version` from config when not passed directly
  - resolves "today" using the config timezone
  - loads the selected model version
  - computes a same-day feature row for one ticker
  - synthesizes a temporary same-day placeholder row if the daily bar for today is missing
  - returns `strength_pct`, `buy_dev_pct=1.0`, `hist_low`, `model_version`
- Added `StrengthSignal` in `app/trend/models.py`
- Added `generate_trend_signal()` placeholder and `generate_strength_signal()` in `app/trend/signal.py`
- `generate_strength_signal()` now maps `strength_pct` in `0.8-1.0` to `buy_strength` in `0.5-1.5`
- `generate_daily_signal()` now accepts optional `strength_signal` and uses:
  - `buy_strength` to scale planned/final buy amount
  - `buy_activate_price` as the target price when provided
- Added tests:
  - `tests/test_buy_sub_ml_inference.py` for runtime ML input assembly
  - `tests/test_trend_signal.py` for strength mapping and target-price behavior
- Verified passing commands:
  - `pytest tests/test_buy_sub_ml_inference.py -q`
  - `pytest tests/test_trend_signal.py -q`
  - `pytest tests/test_backtest_minimal_loop.py -q`
  - `pytest tests/test_compute_trend_features.py -q -k "writes_only_available_trade_dates"`
- Important remaining gap:
  no runtime loop calls the new ML helper yet; integration into paper/live/backtest remains the next step

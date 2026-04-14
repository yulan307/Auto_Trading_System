# Current Status

Last updated: 2026-04-14
Owner: Shared between Claude (day) and Codex (night)

## Active Goal

Phase 1 foundation is complete. Signed percentile fix verified end-to-end with GOOGL inference.
Next focus is Phase 2: expand backtest engine with sell-side logic and position sizing.

## Confirmed Project State

- Foundation, config/database scaffolding, and ML subsystem are fully in place
- `app/trend/features.py` and `app/trend/classifier.py` are implemented
- **All 32 tests pass** (`python -m pytest -q`)
- `feature.db` is currently **empty** (cleared 2026-04-14; re-populate by running `compute_trend_features` per ticker)
- v001 model retrained with 6 tickers (DGRO, JEPI, MSFT, MU, NVDA, SPY), end-date 2026-04-14
- GOOGL inference 2025-01-01 → 2026-04-14: 255 rows, 0 nulls — percentile fix confirmed working

## Signed Percentile Fix (session 3)

Root cause: `compute_signed_rolling_percentile` used a row-count window (256 bars). During sustained
single-direction market periods (e.g., GOOGL 2022–2023 bear market), when values reversed sign in 2025,
the 256-bar history had no same-sign values → NULL output for months.

Fix: Switched to a 365-calendar-day lookback (`PERCENTILE_CALENDAR_WINDOW = 365`). The `dates`
parameter is now required (no fallback). Removed `PERCENTILE_HISTORY_WINDOW`, `compute_total_warmup_bars`,
`--history-window` CLI arg. `TOTAL_WARMUP_BARS` = 500, fetch lookback = 731 calendar days.

## Recommended Next Actions

1. Re-populate `feature.db` for all local tickers before running backtest
   (`python scripts/compute_trend_features.py --tickers DGRO JEPI MSFT MU NVDA SPY --start-date ... --end-date ...`)
2. Review `docs/system_design.md` Phase 2 tasks to pick the next increment
3. Expand backtest engine with sell-side logic and position sizing

## Blockers

None currently.

## Last Known Useful Commands

```bash
python -m pytest -q
python scripts/train_buy_sub_ml.py --tickers DGRO JEPI MSFT MU NVDA SPY --end-date 2026-04-14 --mode new --model v001
python scripts/infer_buy_sub_ml.py --tickers GOOGL --start-date 2025-01-01 --end-date 2026-04-14 --mode infer --model buy/v001
```

## Session End Checklist

- update this file if the active goal changes
- record the latest failing or passing command
- leave the next action in a single sentence

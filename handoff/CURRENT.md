# Current Status

Last updated: 2026-04-14
Owner: Shared between Claude (day) and Codex (night)

## Active Goal

Phase 1 foundation is complete. All 32 tests pass. Signed rolling percentile bug fixed (calendar-window instead of row-count window). Next focus is Phase 2: expand backtest engine with sell-side logic and position sizing.

## Confirmed Project State

- Foundation, config/database scaffolding, and ML subsystem are fully in place
- `app/trend/features.py` and `app/trend/classifier.py` are implemented
- **All 32 tests pass** (`python -m pytest -q`)
- ML training works: `scripts/train_buy_sub_ml.py --tickers SPY DGRO JEPI MSFT MU NVDA --end-date 2026-04-14 --mode new --model v001`
- ML inference works: `scripts/infer_buy_sub_ml.py --tickers GOOGL --start-date 2025-01-01 --end-date 2026-04-14 --mode infer --model buy/v001`
- Available data: DGRO, JEPI, MSFT, MU, NVDA, SPY, GOOGL (daily to 2026-04-09)

## Signed Percentile Fix (this session)

Root cause: `compute_signed_rolling_percentile` used a row-count window (256 bars). During sustained
single-direction market periods (e.g., GOOGL 2022–2023 bear market), when values reversed sign in 2025,
the 256-bar history had no same-sign values → NULL output for months.

Fix: Switched to a 365-calendar-day lookback (`PERCENTILE_CALENDAR_WINDOW = 365`). The `dates`
parameter is now required (no fallback). Updated warmup constants: `_PERCENTILE_WARMUP_BARS = 261`,
`TOTAL_WARMUP_BARS = 500`, `compute_fetch_start_date` now uses `731` calendar-day lookback.
Removed `PERCENTILE_HISTORY_WINDOW`, `compute_total_warmup_bars`, and the `--history-window` CLI arg.

Result: GOOGL null gap (2025-01 to 2025-07-08) reduced from 102 NaN rows to 4 genuine edge cases.

## Recommended Next Actions

1. Review `docs/system_design.md` Phase 2 tasks to pick the next increment
2. Expand backtest engine with sell-side logic and position sizing
3. Retrain models after the percentile fix (old feature.db values used row-count windows)

## Blockers

None currently.

## Last Known Useful Commands

```bash
python -m pytest -q
python scripts/train_buy_sub_ml.py --tickers SPY DGRO JEPI MSFT MU NVDA --end-date 2026-04-14 --mode new --model v001
python scripts/infer_buy_sub_ml.py --tickers GOOGL --start-date 2025-01-01 --end-date 2026-04-14 --mode infer --model buy/v001
```

## Session End Checklist

- update this file if the active goal changes
- record the latest failing or passing command
- leave the next action in a single sentence

# Current Status

Last updated: 2026-04-14
Owner: Shared between Claude (day) and Codex (night)

## Active Goal

Backtest closed loop is now functional (buy + sell). Branch `feature/closed-loop-backtest` is open as PR.
Next: review PR, merge, then move to Phase 2 enhancements (multi-ticker, intraday fill, fee model).

## Confirmed Project State

- Foundation, config/database scaffolding, and ML subsystem are fully in place
- **All 32 tests pass** (`python -m pytest -q`)
- `feature.db` is currently **empty** (cleared 2026-04-14; re-populate via `compute_trend_features`)
- v001 model retrained with 6 tickers (DGRO, JEPI, MSFT, MU, NVDA, SPY), end-date 2026-04-14
- Backtest closed loop works end-to-end: SPY 2025 → 14 buys, cash correctly deducted, JSON output clean

## Closed Loop Fix (session 4 — branch feature/closed-loop-backtest)

**Bugs fixed:**
- JSON crash: `date` in TrendDecision/DailySignal not serializable → added `_to_json_safe()`
- Cash not deducted: `apply_filled_trade` used historical trade_time for snapshot; reset snapshot
  (wall-clock) was always newest → changed to `datetime.now()` for snapshot_time
- Account not reset per run: only reset if snapshot was None → now always `reset_for_backtest()`
  which clears positions + trade_records before writing fresh snapshot

**New features:**
- Sell logic: downtrend sets `action_bias=sell_bias` + `sell_threshold_pct=0.005`; signal.py
  generates sell signal when position held; engine fills on daily high touch (full position)
- `config/backtest.yaml`: added `default_base_trade_amount_usd`, `default_max_position_usd`,
  `default_weekly_budget_multiplier`
- `metrics` now includes `sell_trades` count

## Recommended Next Actions

1. Merge `feature/closed-loop-backtest` PR
2. Re-populate `feature.db` for all local tickers
3. Expand backtest: multi-ticker loop, fee model, intraday 15m fill

## Blockers

None currently.

## Last Known Useful Commands

```bash
python -m pytest -q
python scripts/run_backtest.py --config config/backtest.yaml --ticker SPY --start-date 2025-01-01 --end-date 2025-12-31 --output outputs/backtest_spy_2025.json
```

## Session End Checklist

- update this file if the active goal changes
- record the latest failing or passing command
- leave the next action in a single sentence

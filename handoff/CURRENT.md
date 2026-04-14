# Current Status

Last updated: 2026-04-15
Owner: Shared between Claude (day) and Codex (night)

## Active Goal

Prepare the ML buy-strength runtime path for integration into the trading signal chain on branch
`feature/ml-signal-integration`.
Next: wire the new runtime ML inference into a real entry loop (`run_paper.py`, `run_live.py`, or backtest).

## Confirmed Project State

- Foundation, config/database scaffolding, and ML subsystem are fully in place
- `config/backtest.yaml` already includes:
  - `ml.enabled: true`
  - `ml.buy_model_version: buy/v001`
- `buy_sub_ml` runtime helper is now available via
  `app.ml.buy_sub_ml.inference.infer_buy_strength_signal_inputs()`
- `trend` now has:
  - `generate_trend_signal()` placeholder defaulting to buy
  - `generate_strength_signal()` mapping `strength_pct` from `0.8-1.0` to `0.5-1.5`
  - `generate_daily_signal(..., strength_signal=...)` support for ML-sized buy amounts and
    `buy_activate_price`
- Current runtime behavior for missing same-day daily bar:
  - feature DB still only stores real trade dates
  - runtime ML inference synthesizes a temporary same-day placeholder row so `hist_*` inputs and
    `strength_pct` prediction can still be produced
- Targeted tests passed on 2026-04-15:
  - `pytest tests/test_trend_signal.py -q`
  - `pytest tests/test_buy_sub_ml_inference.py -q`
  - `pytest tests/test_backtest_minimal_loop.py -q`

## ML Runtime Integration

What was added:
- Runtime single-ticker ML inference helper for strength signal inputs
- `StrengthSignal` model in `app/trend/models.py`
- `generate_strength_signal()` in `app/trend/signal.py`
- Buy amount scaling through `buy_strength`
- `buy_activate_price = hist_low * buy_dev_pct` where `buy_dev_pct` currently defaults to `1.0`

What is still not wired end-to-end:
- No runtime loop calls `infer_buy_strength_signal_inputs()` yet
- `generate_trend_signal()` is still a placeholder; backtest still calls `classify_trend()`
- `buy_dev_pct` is still default-only and not yet ML-derived

## Recommended Next Actions

1. Choose the first real integration point: `run_paper.py`, `run_live.py`, or backtest loop
2. Call `infer_buy_strength_signal_inputs()` for the current ticker/date/model version
3. Feed the result into `generate_strength_signal()` and then into `generate_daily_signal()`
4. Decide whether `generate_trend_signal()` should replace or wrap `classify_trend()`

## Blockers

No blocker, but one important design fact remains:
- current feature storage does not persist synthetic same-day rows; the same-day placeholder exists only
  inside runtime ML inference

## Last Known Useful Commands

```bash
pytest tests/test_trend_signal.py -q
pytest tests/test_buy_sub_ml_inference.py -q
pytest tests/test_backtest_minimal_loop.py -q
```

## Session End Checklist

- update this file if the active goal changes
- record the latest failing or passing command
- leave the next action in a single sentence

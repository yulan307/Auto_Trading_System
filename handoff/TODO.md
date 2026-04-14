# TODO

## Now

- Wire `infer_buy_strength_signal_inputs()` into one real runtime path
- Pass ML output through `generate_strength_signal()` before `generate_daily_signal()`
- Decide whether `generate_trend_signal()` becomes the new public trend entry point or remains a wrapper

## Next

- Replace default `buy_dev_pct = 1.0` with a real ML or rules-based source
- Add runtime tests for the chosen integration loop
- Document the same-day placeholder feature-row behavior in `docs/`

## Later

- Reconcile top-level docs with the newer ML runtime architecture
- Expand multi-ticker runtime flow once the single-ticker ML signal path is stable

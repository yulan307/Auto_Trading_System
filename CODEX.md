# CODEX.md

This file provides guidance to Codex when working with code in this repository.

## Working Style

- Prefer small, correct, reviewable patches over broad refactors
- Do not revert unrelated user changes
- Before ending a session, update the shared handoff files in `handoff/`
- If behavior changes, keep docs and handoff notes in sync

## Environment Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/init_db.py --config config/backtest.yaml
```

## Common Commands

```powershell
# Run all tests
python -m pytest -q

# Run a single test
python -m pytest tests/test_infrastructure.py::test_load_config_resolves_project_paths -v

# Reproduce the currently known backtest failure
python -m pytest tests/test_backtest_minimal_loop.py -v

# Initialize databases
python scripts/init_db.py --config config/backtest.yaml

# Compute trend features for a ticker
python scripts/compute_trend_features.py --config config/backtest.yaml --ticker SPY --output-csv

# Train buy-strength ML model
python scripts/train_buy_sub_ml.py --config config/backtest.yaml --non-interactive

# Run inference
python scripts/infer_buy_sub_ml.py --config config/backtest.yaml --ticker SPY --model-reference buy/v001

# Run backtest
python scripts/run_backtest.py --config config/backtest.yaml --ticker SPY --start-date 2025-01-01 --end-date 2025-12-31 --output outputs/result.json
```

## Architecture

The system is a document-driven, locally-backed automated trading system with three runtime modes: **backtest**, **paper**, and **live**. The business logic is intended to stay shared across modes, while startup wiring swaps the injected data, account, and execution backends.

### Layered Structure

```text
config/backtest.yaml
  -> app/runtime/          Runtime init, config loading, path resolution
       -> app/data/        OHLC bar fetching, local SQLite storage, repository
       -> app/symbols/     Symbol metadata and trading constraints
       -> app/account/     Virtual/real account, positions, trade records
       -> app/trend/       MA feature computation, trend signals, budget logic
       -> app/intraday/    15-minute bar tracking (placeholder)
       -> app/execution/   MockBroker (backtest), real broker adapters (future)
       -> app/backtest/    Time-step simulation loop
       -> app/ml/          Buy-strength label generation, model train/infer
       -> app/loggingx/    Structured JSON logging to file + SQLite event store
```

## Config and Data Notes

- `config/backtest.yaml` is the primary config used during current development
- `app.runtime.config_loader.load_config()` merges defaults, resolves project root, and converts relative paths to absolute paths
- Database files are declared under `data:` config and initialized via `scripts/init_db.py`

## Handoff Workflow

Use the root-level `handoff/` directory as the shared relay area between Claude and Codex.

- `handoff/CURRENT.md`: latest objective, blockers, and next actions
- `handoff/TODO.md`: prioritized queue
- `handoff/DECISIONS.md`: decisions worth preserving
- `handoff/SESSION_LOG.md`: short chronological continuity notes

Minimum requirement before ending a Codex session:

1. Update `handoff/CURRENT.md`
2. Append a brief note to `handoff/SESSION_LOG.md`

## Testing Workflow

When changing code, prefer this order:

1. Run the narrowest relevant test first
2. Run adjacent tests if the change affects a module boundary
3. Run `python -m pytest -q` before wrapping up when practical

Record the latest meaningful test result in `handoff/CURRENT.md` if work is still in progress.

## Current Development Status

Current repository guidance says Phase 1 foundation is complete, but the minimal backtest loop is still blocked by missing trend entry points used by `app/backtest/engine.py`.

Start from `handoff/CURRENT.md` for the most recent live status instead of trusting this file alone.

## Documentation

- `docs/system_design.md`: top-level architecture and phased plan
- `docs/api_reference.md`: module integration contracts
- `docs/modules/`: formal module specifications

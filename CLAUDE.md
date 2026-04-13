# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/init_db.py --config config/backtest.yaml
```

## Common Commands

```bash
# Run all tests
python -m pytest -q

# Run a single test
python -m pytest tests/test_infrastructure.py::test_load_config_resolves_project_paths -v

# Initialize databases
python scripts/init_db.py --config config/backtest.yaml

# Compute trend features for a ticker
python scripts/compute_trend_features.py --config config/backtest.yaml --ticker SPY --output-csv

# Train buy-strength ML model (new model named v001, using SPY data up to 2026-01-01)
python scripts/train_buy_sub_ml.py --tickers SPY --end-date 2026-01-01 --mode new --model v001

# Update an existing model (retrain from buy/v001 as base)
python scripts/train_buy_sub_ml.py --tickers SPY --end-date 2026-01-01 --mode update --model buy/v001

# Run inference (non-interactive)
python scripts/infer_buy_sub_ml.py --tickers SPY --start-date 2025-06-01 --end-date 2026-01-01 --mode infer --model buy/v001

# Run backtest
python scripts/run_backtest.py --config config/backtest.yaml --ticker SPY --start-date 2025-01-01 --end-date 2025-12-31 --output outputs/result.json
```

## Architecture

The system is a document-driven, locally-backed automated trading system that supports three runtime modes: **backtest**, **paper**, and **live**. Modes share identical application logic — they differ only in which data source, account source, and execution backend are injected at startup.

### Layered Structure

```
config/backtest.yaml
  └─ app/runtime/          Runtime init, config loading, path resolution
       └─ app/data/        OHLC bar fetching, local SQLite storage, repository
       └─ app/symbols/     Symbol metadata and trading constraints
       └─ app/account/     Virtual/real account, positions, trade records
       └─ app/trend/       MA feature computation, trend signals, budget logic
       └─ app/intraday/    15-minute bar tracking (placeholder)
       └─ app/execution/   MockBroker (backtest), real broker adapters (future)
       └─ app/backtest/    Time-step simulation loop
       └─ app/ml/          Buy-strength label generation, model train/infer
       └─ app/loggingx/    Structured JSON logging to file + SQLite event store
```

### Config System

`config/backtest.yaml` is the primary config. `app.runtime.config_loader.load_config()` deep-merges it with hardcoded defaults, auto-detects project root, and resolves all relative paths to absolute. The three runtime configs (`backtest.yaml`, `paper.yaml`, `live.yaml`) follow the same schema.

### SQLite Databases

All database paths are declared in config under `data:`. Tables are created by `scripts/init_db.py` → `app/data/db.py`.

| DB | Contents |
|----|----------|
| `daily.db` | OHLC bars, daily coverage tracking |
| `feature.db` | MA features, slopes, deviations, percentiles |
| `symbols.db` | Symbol metadata and trading rules |
| `account.db` | Account snapshots, positions, trade records, orders |
| `logs.db` | Structured log events |
| `buy_strength.db` | ML buy-strength label data |

### ML Subsystem (`app/ml/`)

Three-stage pipeline: **label generation** (`buy_strength_label/`) → **training** (`buy_sub_ml/`) → **inference** (`buy_sub_ml/`). Models are versioned under `models/buy/` and `models/sell/`. The public API is exposed via `app/ml/__init__.py`: `get_strength_pct_frame`, `fit_strength_model`, `predict_strength_pct`.

### Key Dataclasses (in respective `models.py` files)

`OHLCVBar`, `SymbolInfo`, `AccountSnapshot`, `Position`, `TradeRecord`, `OrderRequest`, `OrderStatus`, `TrendDecision`, `DailySignal`, `LogEvent`

## Current Development Status

Phase 1 foundation is complete. All 32 tests pass. The ML subsystem is end-to-end functional:
- `app/trend/classifier.py` and `app/trend/features.py` are implemented
- `tests/test_backtest_minimal_loop.py` passes
- Training (`scripts/train_buy_sub_ml.py`) and inference (`scripts/infer_buy_sub_ml.py`) scripts run successfully end-to-end
- A trained model `buy/v001` exists under `models/buy/v001/`

Current focus: expanding the backtest engine toward a full closed-loop simulation (Phase 2).

## Documentation

Formal module specifications live in `docs/modules/`. `docs/system_design.md` covers the top-level architecture and 7-phase development plan. `docs/api_reference.md` documents the module integration contracts.

## Agent Handoff

Use the root-level `handoff/` directory as the shared handoff area between Claude and Codex.

- `handoff/CURRENT.md`: the latest working context, current goal, blockers, and the next 1-3 concrete actions
- `handoff/TODO.md`: prioritized task queue
- `handoff/DECISIONS.md`: important decisions and tradeoffs that should not be rediscovered
- `handoff/SESSION_LOG.md`: compact session-by-session notes for quick continuity

Before ending a work session, update `handoff/CURRENT.md` and append a short entry to `handoff/SESSION_LOG.md`.

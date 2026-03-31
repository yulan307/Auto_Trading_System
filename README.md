# Auto Trading System

This repository contains the foundation of a document-driven trading system.

Phase 1 includes:
- project skeleton and package layout
- core dataclass schemas
- SQLite database bootstrap
- structured logging
- YAML config loading
- manual-only GitHub workflow

## Quick Start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/init_db.py --config config/backtest.yaml
pytest
```

## Current Scope

Only the first development phase from `auto_trading_system_implementation_spec.md` is implemented. Data fetching, symbol management, virtual account logic, and backtest logic are intentionally kept as placeholders for the following phases.

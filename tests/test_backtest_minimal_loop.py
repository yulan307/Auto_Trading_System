from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.backtest.engine import run_backtest
from app.data.db import initialize_all_databases
from app.data.repository import save_bars
from app.loggingx.logger import setup_logging
from scripts.run_backtest import _ensure_daily_data_ready


def _build_test_config(tmp_path: Path) -> dict:
    return {
        "mode": "backtest",
        "timezone": "America/New_York",
        "data": {
            "daily_db_path": str(tmp_path / "daily.db"),
            "intraday_db_path": str(tmp_path / "intraday.db"),
            "symbols_db_path": str(tmp_path / "symbols.db"),
            "account_db_path": str(tmp_path / "account.db"),
            "logs_db_path": str(tmp_path / "logs.db"),
        },
        "account": {"initial_cash": 100000},
        "execution": {"allow_fractional_default": False},
        "logging": {"log_level": "INFO", "log_dir": str(tmp_path / "logs")},
        "strategy": {
            "default_base_trade_amount_usd": 1000,
            "default_max_position_usd": 5000,
            "default_weekly_budget_multiplier": 3,
        },
    }


def test_minimal_backtest_loop_runs_end_to_end(tmp_path: Path) -> None:
    config = _build_test_config(tmp_path)
    initialize_all_databases(config)

    start_dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i in range(80):
        close = 100.0 + i * 0.5
        open_price = close * 0.998
        bars.append(
            {
                "ticker": "SPY",
                "datetime": start_dt + timedelta(days=i),
                "interval": "1d",
                "open": open_price,
                "high": close * 1.01,
                "low": close * 0.985,
                "close": close,
                "volume": 1_000_000,
                "source": "test",
                "update_time": start_dt + timedelta(days=i),
            }
        )

    saved = save_bars(config["data"]["daily_db_path"], "daily_bars", bars)
    assert saved == 80

    logger = setup_logging(config)
    runtime_context = {"mode": "backtest", "config": config, "logger": logger}

    result = run_backtest(
        ticker="SPY",
        start_date="2025-01-01",
        end_date="2025-03-31",
        runtime_context=runtime_context,
    )
    logger.shutdown()

    assert result["status"] == "completed"
    assert result["metrics"]["bars"] == 80
    assert result["metrics"]["decision_days"] == 18
    assert "total_return_pct" in result["metrics"]
    assert isinstance(result["trades"], list)


def test_backtest_init_requires_data_when_local_provider(tmp_path: Path) -> None:
    config = _build_test_config(tmp_path)
    initialize_all_databases(config)

    try:
        _ensure_daily_data_ready(
            config=config,
            ticker="SPY",
            start_date="2025-01-01",
            end_date="2025-01-31",
        )
    except RuntimeError as exc:
        assert "No daily bars available" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when local provider has no data")


def test_backtest_init_detects_local_data_presence(tmp_path: Path) -> None:
    config = _build_test_config(tmp_path)
    initialize_all_databases(config)

    base_dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(3):
        rows.append(
            {
                "ticker": "SPY",
                "datetime": base_dt + timedelta(days=i),
                "interval": "1d",
                "open": 100 + i,
                "high": 101 + i,
                "low": 99 + i,
                "close": 100.5 + i,
                "volume": 1000,
                "source": "test",
                "update_time": base_dt + timedelta(days=i),
            }
        )
    save_bars(config["data"]["daily_db_path"], "daily_bars", rows)

    result = _ensure_daily_data_ready(
        config=config,
        ticker="SPY",
        start_date="2025-01-01",
        end_date="2025-01-31",
    )
    assert result["available_bars"] == 3

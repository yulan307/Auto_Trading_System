from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from app.data.db import initialize_all_databases
from app.data.models import OHLCVBar
from app.loggingx.logger import setup_logging
from app.runtime.config_loader import load_config
from app.symbols.models import SymbolInfo


def test_load_config_resolves_project_paths() -> None:
    expected_root = Path(__file__).resolve().parents[1]
    config = load_config("config/backtest.yaml")

    assert config["mode"] == "backtest"
    assert Path(config["data"]["daily_db_path"]).name == "daily.db"
    assert Path(config["data"]["feature_db_path"]).name == "feature.db"
    assert Path(config["logging"]["log_dir"]).name == "logs"
    assert Path(config["project_root"]) == expected_root


def test_initialize_all_databases_creates_expected_tables(tmp_path: Path) -> None:
    config = {
        "data": {
            "daily_db_path": str(tmp_path / "daily.db"),
            "intraday_db_path": str(tmp_path / "intraday.db"),
            "symbols_db_path": str(tmp_path / "symbols.db"),
            "account_db_path": str(tmp_path / "account.db"),
            "logs_db_path": str(tmp_path / "logs.db"),
        }
    }

    initialize_all_databases(config)

    with sqlite3.connect(tmp_path / "daily.db") as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"daily_bars", "daily_coverage"} <= tables

    with sqlite3.connect(tmp_path / "account.db") as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"account_snapshots", "positions", "trade_records", "orders"} <= tables

    with sqlite3.connect(tmp_path / "logs.db") as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "log_events" in tables


def test_logger_writes_file_and_event_store(tmp_path: Path) -> None:
    config = {
        "logging": {"log_level": "INFO", "log_dir": str(tmp_path / "logs")},
        "data": {"logs_db_path": str(tmp_path / "logs.db")},
    }
    logger = setup_logging(config)

    logger.log_event(
        level="INFO",
        module="tests",
        event_type="system_init",
        message="logger works",
        ticker="SPY",
        payload={"ok": True},
    )
    logger.shutdown()

    app_log = tmp_path / "logs" / "app.log"
    assert app_log.exists()
    assert "logger works" in app_log.read_text(encoding="utf-8")

    with sqlite3.connect(tmp_path / "logs.db") as connection:
        row = connection.execute("SELECT module, event_type, ticker, message FROM log_events").fetchone()
        assert row == ("tests", "system_init", "SPY", "logger works")


def test_models_validate_constraints() -> None:
    bar = OHLCVBar(
        datetime=datetime(2026, 1, 1, 9, 30),
        ticker="SPY",
        interval="1d",
        open=100,
        high=105,
        low=99,
        close=104,
        volume=1000,
        source="local",
        update_time=datetime(2026, 1, 1, 16, 0),
    )
    assert bar.high == 105.0

    symbol = SymbolInfo(
        symbol="SPY",
        market="US",
        asset_type="etf",
        currency="USD",
        timezone="America/New_York",
        base_trade_amount_usd=1000,
        max_position_usd=2000,
        weekly_budget_multiplier=1.5,
    )
    assert symbol.symbol == "SPY"

    with pytest.raises(ValueError):
        OHLCVBar(
            datetime=datetime(2026, 1, 1, 9, 30),
            ticker="SPY",
            interval="1d",
            open=100,
            high=90,
            low=91,
            close=95,
            volume=1000,
            source="local",
            update_time=datetime(2026, 1, 1, 16, 0),
        )

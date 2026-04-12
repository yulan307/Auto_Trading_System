from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


PRICE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table_name} (
    ticker TEXT NOT NULL,
    datetime TEXT NOT NULL,
    interval TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    source TEXT NOT NULL,
    update_time TEXT NOT NULL,
    PRIMARY KEY (ticker, interval, datetime)
);
CREATE INDEX IF NOT EXISTS idx_{table_name}_ticker_datetime ON {table_name} (ticker, datetime);
"""

SYMBOLS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS symbols (
    symbol TEXT PRIMARY KEY,
    market TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    currency TEXT NOT NULL,
    timezone TEXT NOT NULL,
    enabled_for_backtest INTEGER NOT NULL,
    enabled_for_live INTEGER NOT NULL,
    enabled_for_paper INTEGER NOT NULL,
    tags TEXT NOT NULL,
    data_provider TEXT,
    broker_route TEXT,
    strategy_profile TEXT,
    base_trade_amount_usd REAL,
    max_position_usd REAL,
    weekly_budget_multiplier REAL,
    allow_force_buy_last_bar INTEGER NOT NULL,
    allow_fractional INTEGER NOT NULL
);
"""

ACCOUNT_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS account_snapshots (
    snapshot_time TEXT NOT NULL,
    mode TEXT NOT NULL,
    account_id TEXT NOT NULL,
    cash_available REAL NOT NULL,
    cash_total REAL NOT NULL,
    equity_value REAL NOT NULL,
    market_value REAL NOT NULL,
    total_asset REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    ticker TEXT PRIMARY KEY,
    quantity REAL NOT NULL,
    avg_cost REAL NOT NULL,
    market_price REAL NOT NULL,
    market_value REAL NOT NULL,
    unrealized_pnl REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_records (
    trade_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    amount REAL NOT NULL,
    fee REAL NOT NULL,
    trade_time TEXT NOT NULL,
    mode TEXT NOT NULL,
    broker TEXT NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    status TEXT NOT NULL,
    submit_time TEXT NOT NULL,
    update_time TEXT NOT NULL,
    submitted_price REAL,
    avg_fill_price REAL,
    filled_quantity REAL NOT NULL,
    filled_amount REAL NOT NULL,
    broker_message TEXT
);
"""

LOG_EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS log_events (
    event_time TEXT NOT NULL,
    level TEXT NOT NULL,
    module TEXT NOT NULL,
    event_type TEXT NOT NULL,
    ticker TEXT,
    message TEXT NOT NULL,
    payload_json TEXT
);
"""


def connect_sqlite(db_path: str | Path) -> sqlite3.Connection:
    target = Path(db_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def init_price_db(db_path: str | Path, table_name: str) -> None:
    with connect_sqlite(db_path) as connection:
        connection.executescript(PRICE_TABLE_SQL.format(table_name=table_name))


def init_symbols_db(db_path: str | Path) -> None:
    with connect_sqlite(db_path) as connection:
        connection.executescript(SYMBOLS_TABLE_SQL)


def init_account_db(db_path: str | Path) -> None:
    with connect_sqlite(db_path) as connection:
        connection.executescript(ACCOUNT_TABLES_SQL)


def init_logs_db(db_path: str | Path) -> None:
    with connect_sqlite(db_path) as connection:
        connection.executescript(LOG_EVENTS_TABLE_SQL)


def initialize_all_databases(config: dict[str, Any]) -> dict[str, str]:
    data_config = config["data"]
    init_price_db(data_config["daily_db_path"], "daily_bars")
    init_price_db(data_config["intraday_db_path"], "intraday_bars")
    init_symbols_db(data_config["symbols_db_path"])
    init_account_db(data_config["account_db_path"])
    init_logs_db(data_config["logs_db_path"])
    return {
        "daily_db_path": data_config["daily_db_path"],
        "feature_db_path": data_config.get("feature_db_path", ""),
        "intraday_db_path": data_config["intraday_db_path"],
        "symbols_db_path": data_config["symbols_db_path"],
        "account_db_path": data_config["account_db_path"],
        "logs_db_path": data_config["logs_db_path"],
    }

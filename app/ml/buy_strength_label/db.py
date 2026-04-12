from __future__ import annotations

from app.data.db import connect_sqlite
from app.ml.common.schemas import BUY_STRENGTH_TABLE_NAME
from app.ml.common.utils import validate_sqlite_identifier


def create_buy_strength_table_sql(table_name: str = BUY_STRENGTH_TABLE_NAME) -> str:
    validated = validate_sqlite_identifier(table_name)
    return f"""
    CREATE TABLE IF NOT EXISTS {validated} (
        ticker TEXT NOT NULL,
        date TEXT NOT NULL,
        strength REAL NOT NULL,
        label_version TEXT,
        update_time TEXT NOT NULL,
        PRIMARY KEY (ticker, date)
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_{validated}_ticker_date
    ON {validated} (ticker, date);
    CREATE INDEX IF NOT EXISTS idx_{validated}_ticker
    ON {validated} (ticker);
    """


def ensure_buy_strength_table(
    db_path: str,
    table_name: str = BUY_STRENGTH_TABLE_NAME,
) -> None:
    with connect_sqlite(db_path) as connection:
        connection.executescript(create_buy_strength_table_sql(table_name=table_name))

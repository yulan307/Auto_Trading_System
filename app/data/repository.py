from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.data.db import connect_sqlite, init_price_db


TABLE_BY_INTERVAL = {"1d": "daily_bars", "15m": "intraday_bars"}


def _to_iso(dt: Any) -> str:
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def save_bars(db_path: str | Path, table_name: str, bars: list[dict[str, Any]]) -> int:
    if not bars:
        return 0

    sql = f"""
    INSERT INTO {table_name}
    (ticker, datetime, interval, open, high, low, close, volume, source, update_time)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(ticker, interval, datetime) DO UPDATE SET
        open=excluded.open,
        high=excluded.high,
        low=excluded.low,
        close=excluded.close,
        volume=excluded.volume,
        source=excluded.source,
        update_time=excluded.update_time
    """

    values = [
        (
            row["ticker"],
            _to_iso(row["datetime"]),
            row["interval"],
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            float(row["volume"]),
            row["source"],
            _to_iso(row["update_time"]),
        )
        for row in bars
    ]

    with connect_sqlite(db_path) as connection:
        connection.executemany(sql, values)
    return len(values)


def load_bars(
    db_path: str | Path,
    table_name: str,
    ticker: str,
    interval: str,
    start_date: str | datetime | None = None,
    end_date: str | datetime | None = None,
) -> list[dict[str, Any]]:
    conditions = ["ticker = ?", "interval = ?"]
    params: list[Any] = [ticker, interval]

    if start_date is not None:
        conditions.append("datetime >= ?")
        params.append(_to_iso(start_date))
    if end_date is not None:
        conditions.append("datetime <= ?")
        params.append(_to_iso(end_date))

    where_sql = " AND ".join(conditions)
    sql = f"SELECT * FROM {table_name} WHERE {where_sql} ORDER BY datetime ASC"

    with connect_sqlite(db_path) as connection:
        rows = connection.execute(sql, params).fetchall()
    return [dict(row) for row in rows]

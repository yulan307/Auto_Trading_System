from __future__ import annotations

from typing import Any

import pandas as pd

from app.data.db import connect_sqlite
from app.ml.buy_strength_label.init_db import init_buy_strength_db
from app.ml.common.paths import DEFAULT_BUY_STRENGTH_DB_PATH
from app.ml.common.schemas import BUY_STRENGTH_TABLE_NAME
from app.ml.common.utils import coerce_date_str, normalize_tickers, validate_sqlite_identifier


EXPECTED_COLUMNS = ["ticker", "date", "strength", "label_version", "update_time"]


def _normalize_strength_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    missing = [column for column in EXPECTED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Strength frame missing required columns: {missing}")
    frame = frame.loc[:, EXPECTED_COLUMNS].copy()
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if frame["date"].isna().any():
        raise ValueError("Found invalid date values in strength rows.")
    frame["strength"] = pd.to_numeric(frame["strength"], errors="coerce")
    if frame["strength"].isna().any():
        raise ValueError("Found non-numeric strength values.")
    frame["label_version"] = frame["label_version"].astype(str)
    frame["update_time"] = frame["update_time"].astype(str)
    return frame


def upsert_strength_rows(
    df: pd.DataFrame,
    db_path: str = str(DEFAULT_BUY_STRENGTH_DB_PATH),
    table_name: str = BUY_STRENGTH_TABLE_NAME,
) -> int:
    if df.empty:
        return 0

    frame = _normalize_strength_frame(df)
    validated = validate_sqlite_identifier(table_name)
    init_buy_strength_db(db_path=db_path, table_name=validated)
    sql = (
        f"INSERT INTO {validated} (ticker, date, strength, label_version, update_time) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(ticker, date) DO UPDATE SET "
        "strength=excluded.strength, "
        "label_version=excluded.label_version, "
        "update_time=excluded.update_time"
    )
    records = list(frame.itertuples(index=False, name=None))
    with connect_sqlite(db_path) as connection:
        connection.executemany(sql, records)
    return len(records)


def load_strength_rows(
    tickers: str | list[str],
    start_date: str,
    end_date: str,
    db_path: str = str(DEFAULT_BUY_STRENGTH_DB_PATH),
    table_name: str = BUY_STRENGTH_TABLE_NAME,
) -> pd.DataFrame:
    validated = validate_sqlite_identifier(table_name)
    normalized_tickers = normalize_tickers(tickers)
    init_buy_strength_db(db_path=db_path, table_name=validated)
    start = coerce_date_str(start_date)
    end = coerce_date_str(end_date)
    placeholders = ", ".join("?" for _ in normalized_tickers)
    sql = (
        f"SELECT ticker, date, strength, label_version, update_time "
        f"FROM {validated} "
        f"WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ? "
        "ORDER BY ticker ASC, date ASC"
    )
    params: list[Any] = [*normalized_tickers, start, end]
    with connect_sqlite(db_path) as connection:
        frame = pd.read_sql_query(sql, connection, params=params)
    if frame.empty:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    return frame.loc[:, EXPECTED_COLUMNS].copy()


def get_existing_strength_dates(
    ticker: str,
    start_date: str,
    end_date: str,
    db_path: str = str(DEFAULT_BUY_STRENGTH_DB_PATH),
    table_name: str = BUY_STRENGTH_TABLE_NAME,
) -> set[str]:
    frame = load_strength_rows(
        tickers=ticker,
        start_date=start_date,
        end_date=end_date,
        db_path=db_path,
        table_name=table_name,
    )
    return set(frame["date"].astype(str).tolist())

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from app.data.db import connect_sqlite, init_daily_coverage_table, init_price_db
from app.data.providers.yfinance_provider import YFinanceProvider
from app.data.repository import load_bars, save_bars
from app.data.schema import normalize_ohlcv_dataframe


TABLE_BY_INTERVAL = {"1d": "daily_bars", "15m": "intraday_bars"}
VALID_COVERAGE_STATUS = "valid"
MISSING_COVERAGE_STATUS = "checked_missing"


def _coerce_date(value: date | datetime | str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.fromisoformat(str(value)).date()


def _iter_calendar_dates(start_date: date, end_date: date) -> Iterable[date]:
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


def _group_contiguous_dates(dates: list[date]) -> list[tuple[date, date]]:
    if not dates:
        return []

    ordered = sorted(dates)
    groups: list[tuple[date, date]] = []
    group_start = ordered[0]
    previous = ordered[0]

    for current in ordered[1:]:
        if current == previous + timedelta(days=1):
            previous = current
            continue
        groups.append((group_start, previous))
        group_start = current
        previous = current

    groups.append((group_start, previous))
    return groups


def _load_coverage_map(
    *,
    db_path: str | Path,
    ticker: str,
    interval: str,
    start_date: date,
    end_date: date,
) -> dict[date, str]:
    with connect_sqlite(db_path) as connection:
        rows = connection.execute(
            """
            SELECT date, status
            FROM daily_coverage
            WHERE ticker = ? AND interval = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
            """,
            (ticker, interval, start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
    return {date.fromisoformat(str(row["date"])): str(row["status"]) for row in rows}


def _save_coverage_rows(db_path: str | Path, rows: list[dict[str, str]]) -> int:
    if not rows:
        return 0

    sql = """
    INSERT INTO daily_coverage (ticker, interval, date, status, source, checked_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(ticker, interval, date) DO UPDATE SET
        status=excluded.status,
        source=excluded.source,
        checked_at=excluded.checked_at
    """
    values = [
        (
            row["ticker"],
            row["interval"],
            row["date"],
            row["status"],
            row["source"],
            row["checked_at"],
        )
        for row in rows
    ]
    with connect_sqlite(db_path) as connection:
        connection.executemany(sql, values)
    return len(values)


def _seed_valid_coverage_from_existing_bars(
    *,
    db_path: str | Path,
    ticker: str,
    interval: str,
    start_date: date,
    end_date: date,
) -> int:
    bars = load_bars(
        db_path=db_path,
        table_name=TABLE_BY_INTERVAL[interval],
        ticker=ticker,
        interval=interval,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )
    if not bars:
        return 0

    coverage_rows = []
    for row in bars:
        bar_date = _coerce_date(str(row["datetime"]))
        coverage_rows.append(
            {
                "ticker": ticker,
                "interval": interval,
                "date": bar_date.isoformat(),
                "status": VALID_COVERAGE_STATUS,
                "source": str(row.get("source", "seed")),
                "checked_at": str(row.get("update_time", datetime.now(timezone.utc).isoformat())),
            }
        )
    return _save_coverage_rows(db_path, coverage_rows)


def update_symbol_data(
    *,
    provider,
    db_path: str,
    ticker: str,
    interval: str,
    start_date: date | datetime,
    end_date: date | datetime,
    source: str,
) -> dict[str, Any]:
    if interval not in TABLE_BY_INTERVAL:
        raise ValueError(f"Unsupported interval: {interval}")

    raw_rows = provider.fetch_bars(ticker=ticker, interval=interval, start_date=start_date, end_date=end_date)
    normalized = normalize_ohlcv_dataframe(raw_rows, ticker=ticker, interval=interval, source=source)
    saved = save_bars(db_path, TABLE_BY_INTERVAL[interval], normalized)

    return {
        "ticker": ticker,
        "interval": interval,
        "fetched": len(raw_rows),
        "saved": saved,
        "table": TABLE_BY_INTERVAL[interval],
    }


def update_daily_db(
    ticker: str,
    start_date: date | datetime | str,
    end_date: date | datetime | str,
    *,
    db_path: str | Path,
    provider=None,
    source: str = "yfinance",
    interval: str = "1d",
) -> dict[str, Any]:
    if interval != "1d":
        raise ValueError("update_daily_db currently only supports interval='1d'.")

    start = _coerce_date(start_date)
    end = _coerce_date(end_date)
    if end < start:
        raise ValueError("end_date must be greater than or equal to start_date.")

    active_provider = provider or YFinanceProvider()

    init_price_db(db_path, TABLE_BY_INTERVAL[interval])
    init_daily_coverage_table(db_path)
    _seed_valid_coverage_from_existing_bars(
        db_path=db_path,
        ticker=ticker,
        interval=interval,
        start_date=start,
        end_date=end,
    )
    coverage_map = _load_coverage_map(
        db_path=db_path,
        ticker=ticker,
        interval=interval,
        start_date=start,
        end_date=end,
    )

    unchecked_dates = [
        current_date
        for current_date in _iter_calendar_dates(start, end)
        if current_date not in coverage_map
    ]
    weekend_dates = [current_date for current_date in unchecked_dates if current_date.weekday() >= 5]
    fetch_dates = [current_date for current_date in unchecked_dates if current_date.weekday() < 5]
    missing_segments = _group_contiguous_dates(fetch_dates)

    fetched_rows = 0
    saved_rows = 0
    coverage_rows_written = 0

    if weekend_dates:
        checked_at = datetime.now(timezone.utc).isoformat()
        coverage_rows_written += _save_coverage_rows(
            db_path,
            [
                {
                    "ticker": ticker,
                    "interval": interval,
                    "date": current_date.isoformat(),
                    "status": MISSING_COVERAGE_STATUS,
                    "source": source,
                    "checked_at": checked_at,
                }
                for current_date in weekend_dates
            ],
        )

    for segment_start, segment_end in missing_segments:
        raw_rows = active_provider.fetch_bars(
            ticker=ticker,
            interval=interval,
            start_date=segment_start,
            end_date=segment_end,
        )
        normalized = normalize_ohlcv_dataframe(raw_rows, ticker=ticker, interval=interval, source=source)
        fetched_rows += len(raw_rows)
        saved_rows += save_bars(db_path, TABLE_BY_INTERVAL[interval], normalized)

        valid_dates = {_coerce_date(row["datetime"]) for row in normalized}
        checked_at = datetime.now(timezone.utc).isoformat()
        coverage_rows = []
        for current_date in _iter_calendar_dates(segment_start, segment_end):
            coverage_rows.append(
                {
                    "ticker": ticker,
                    "interval": interval,
                    "date": current_date.isoformat(),
                    "status": VALID_COVERAGE_STATUS if current_date in valid_dates else MISSING_COVERAGE_STATUS,
                    "source": source,
                    "checked_at": checked_at,
                }
            )
        coverage_rows_written += _save_coverage_rows(db_path, coverage_rows)

    return {
        "ticker": ticker,
        "interval": interval,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "segments_checked": len(missing_segments),
        "fetched": fetched_rows,
        "saved": saved_rows,
        "coverage_rows_written": coverage_rows_written,
    }

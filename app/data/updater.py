from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.data.repository import save_bars
from app.data.schema import normalize_ohlcv_dataframe


TABLE_BY_INTERVAL = {"1d": "daily_bars", "15m": "intraday_bars"}


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

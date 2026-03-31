from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

REQUIRED_COLUMNS = {"datetime", "open", "high", "low", "close", "volume"}


def _coerce_rows(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return [dict(row) for row in data]

    to_dict = getattr(data, "to_dict", None)
    if callable(to_dict):
        try:
            rows = to_dict(orient="records")
        except TypeError:
            rows = to_dict("records")
        return [dict(row) for row in rows]

    raise TypeError("bars must be a list[dict] or a dataframe-like object supporting to_dict.")


def normalize_ohlcv_dataframe(
    bars: Any,
    *,
    ticker: str,
    interval: str,
    source: str,
    update_time: datetime | None = None,
) -> list[dict[str, Any]]:
    rows = _coerce_rows(bars)
    if not rows:
        return []

    normalized: list[dict[str, Any]] = []
    for row in rows:
        if "Datetime" in row and "datetime" not in row:
            row["datetime"] = row["Datetime"]
        if "Date" in row and "datetime" not in row:
            row["datetime"] = row["Date"]
        missing = [c for c in REQUIRED_COLUMNS if c not in row]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        dt = row["datetime"]
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)

        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        volume = float(row["volume"])
        if high < max(open_price, close, low):
            raise ValueError("high must be >= open/close/low")
        if low > min(open_price, close, high):
            raise ValueError("low must be <= open/close/high")

        normalized.append(
            {
                "datetime": dt,
                "ticker": ticker,
                "interval": interval,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "source": source,
                "update_time": update_time or datetime.now(timezone.utc),
            }
        )

    normalized.sort(key=lambda x: x["datetime"])
    deduped: dict[datetime, dict[str, Any]] = {}
    for row in normalized:
        deduped[row["datetime"]] = row
    return list(deduped.values())

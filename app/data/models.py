from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.utils.validation import ensure_non_empty_string, ensure_numeric


@dataclass(slots=True)
class OHLCVBar:
    datetime: datetime
    ticker: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    update_time: datetime

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.ticker, "ticker")
        ensure_non_empty_string(self.interval, "interval")
        ensure_non_empty_string(self.source, "source")

        self.open = ensure_numeric(self.open, "open")
        self.high = ensure_numeric(self.high, "high")
        self.low = ensure_numeric(self.low, "low")
        self.close = ensure_numeric(self.close, "close")
        self.volume = ensure_numeric(self.volume, "volume")

        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be greater than or equal to open, close, and low.")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be less than or equal to open, close, and high.")

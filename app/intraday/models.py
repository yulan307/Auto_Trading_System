from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.utils.validation import ensure_non_empty_string


@dataclass(slots=True)
class IntradayState:
    ticker: str
    trade_date: str
    tracking_side: str
    tracked_low: float | None
    tracked_high: float | None
    current_order_id: str | None
    order_active: bool
    entered_trade: bool
    force_trade_enabled: bool
    last_bar_time: datetime | None
    note: str | None = None

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.ticker, "ticker")
        ensure_non_empty_string(self.trade_date, "trade_date")
        ensure_non_empty_string(self.tracking_side, "tracking_side")

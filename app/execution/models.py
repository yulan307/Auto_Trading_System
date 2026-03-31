from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.utils.validation import ensure_non_empty_string, ensure_numeric


@dataclass(slots=True)
class OrderRequest:
    ticker: str
    side: str
    order_type: str
    price: float | None
    amount_usd: float
    quantity: float | None
    reason: str
    strategy_tag: str | None = None

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.ticker, "ticker")
        ensure_non_empty_string(self.reason, "reason")
        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'.")
        if self.order_type not in {"market", "limit"}:
            raise ValueError("order_type must be 'market' or 'limit'.")
        self.amount_usd = ensure_numeric(self.amount_usd, "amount_usd")
        if self.price is not None:
            self.price = ensure_numeric(self.price, "price")
        if self.quantity is not None:
            self.quantity = ensure_numeric(self.quantity, "quantity")


@dataclass(slots=True)
class OrderStatus:
    order_id: str
    ticker: str
    side: str
    status: str
    submit_time: datetime
    update_time: datetime
    submitted_price: float | None
    avg_fill_price: float | None
    filled_quantity: float
    filled_amount: float
    broker_message: str | None = None

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.order_id, "order_id")
        ensure_non_empty_string(self.ticker, "ticker")
        ensure_non_empty_string(self.side, "side")
        ensure_non_empty_string(self.status, "status")
        self.filled_quantity = ensure_numeric(self.filled_quantity, "filled_quantity")
        self.filled_amount = ensure_numeric(self.filled_amount, "filled_amount")

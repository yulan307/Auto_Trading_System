from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.utils.validation import ensure_non_empty_string, ensure_numeric


@dataclass(slots=True)
class AccountSnapshot:
    snapshot_time: datetime
    mode: str
    account_id: str
    cash_available: float
    cash_total: float
    equity_value: float
    market_value: float
    total_asset: float

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.mode, "mode")
        ensure_non_empty_string(self.account_id, "account_id")
        self.cash_available = ensure_numeric(self.cash_available, "cash_available")
        self.cash_total = ensure_numeric(self.cash_total, "cash_total")
        self.equity_value = ensure_numeric(self.equity_value, "equity_value")
        self.market_value = ensure_numeric(self.market_value, "market_value")
        self.total_asset = ensure_numeric(self.total_asset, "total_asset")


@dataclass(slots=True)
class Position:
    ticker: str
    quantity: float
    avg_cost: float
    market_price: float
    market_value: float
    unrealized_pnl: float

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.ticker, "ticker")
        self.quantity = ensure_numeric(self.quantity, "quantity")
        self.avg_cost = ensure_numeric(self.avg_cost, "avg_cost")
        self.market_price = ensure_numeric(self.market_price, "market_price")
        self.market_value = ensure_numeric(self.market_value, "market_value")
        self.unrealized_pnl = ensure_numeric(self.unrealized_pnl, "unrealized_pnl")


@dataclass(slots=True)
class TradeRecord:
    trade_id: str
    order_id: str
    ticker: str
    side: str
    quantity: float
    price: float
    amount: float
    fee: float
    trade_time: datetime
    mode: str
    broker: str
    note: str | None = None

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.trade_id, "trade_id")
        ensure_non_empty_string(self.order_id, "order_id")
        ensure_non_empty_string(self.ticker, "ticker")
        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'.")
        ensure_non_empty_string(self.mode, "mode")
        ensure_non_empty_string(self.broker, "broker")
        self.quantity = ensure_numeric(self.quantity, "quantity")
        self.price = ensure_numeric(self.price, "price")
        self.amount = ensure_numeric(self.amount, "amount")
        self.fee = ensure_numeric(self.fee, "fee")

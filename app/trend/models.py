from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.utils.validation import ensure_non_empty_string, ensure_numeric


@dataclass(slots=True)
class TrendDecision:
    trade_date: date
    ticker: str
    trend_type: str
    trend_strength: float
    action_bias: str
    buy_threshold_pct: float | None
    sell_threshold_pct: float | None
    rebound_pct: float | None
    budget_multiplier: float
    reason: str

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.ticker, "ticker")
        ensure_non_empty_string(self.trend_type, "trend_type")
        ensure_non_empty_string(self.action_bias, "action_bias")
        ensure_non_empty_string(self.reason, "reason")
        self.trend_strength = ensure_numeric(self.trend_strength, "trend_strength")
        self.budget_multiplier = ensure_numeric(self.budget_multiplier, "budget_multiplier")


@dataclass(slots=True)
class DailySignal:
    trade_date: date
    ticker: str
    action: str
    target_price: float | None
    planned_amount_usd: float
    allowed_cash_today: float
    final_amount_usd: float
    reason: str

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.ticker, "ticker")
        ensure_non_empty_string(self.action, "action")
        ensure_non_empty_string(self.reason, "reason")
        self.planned_amount_usd = ensure_numeric(self.planned_amount_usd, "planned_amount_usd")
        self.allowed_cash_today = ensure_numeric(self.allowed_cash_today, "allowed_cash_today")
        self.final_amount_usd = ensure_numeric(self.final_amount_usd, "final_amount_usd")


@dataclass(slots=True)
class StrengthSignal:
    trade_date: date
    ticker: str
    strength_pct: float
    buy_strength: float
    buy_dev_pct: float
    buy_activate_price: float | None
    reason: str

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.ticker, "ticker")
        ensure_non_empty_string(self.reason, "reason")
        self.strength_pct = ensure_numeric(self.strength_pct, "strength_pct")
        self.buy_strength = ensure_numeric(self.buy_strength, "buy_strength")
        self.buy_dev_pct = ensure_numeric(self.buy_dev_pct, "buy_dev_pct")
        if self.buy_activate_price is not None:
            self.buy_activate_price = ensure_numeric(self.buy_activate_price, "buy_activate_price")

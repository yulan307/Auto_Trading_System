from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.utils.validation import ensure_non_empty_string, ensure_numeric


@dataclass(slots=True)
class TrendFeatures:
    trade_date: date
    ticker: str
    close: float
    ma5: float
    ma20: float
    ma60: float
    slope5: float
    slope20: float
    slope60: float
    ma_order_code: str
    slope_code: str

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.ticker, "ticker")
        ensure_non_empty_string(self.ma_order_code, "ma_order_code")
        ensure_non_empty_string(self.slope_code, "slope_code")
        self.close = ensure_numeric(self.close, "close")
        self.ma5 = ensure_numeric(self.ma5, "ma5")
        self.ma20 = ensure_numeric(self.ma20, "ma20")
        self.ma60 = ensure_numeric(self.ma60, "ma60")
        self.slope5 = ensure_numeric(self.slope5, "slope5")
        self.slope20 = ensure_numeric(self.slope20, "slope20")
        self.slope60 = ensure_numeric(self.slope60, "slope60")


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

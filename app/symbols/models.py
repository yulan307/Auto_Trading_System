from __future__ import annotations

from dataclasses import dataclass, field

from app.utils.validation import ensure_non_empty_string, ensure_positive_or_none


@dataclass(slots=True)
class SymbolInfo:
    symbol: str
    market: str
    asset_type: str
    currency: str
    timezone: str
    enabled_for_backtest: bool = True
    enabled_for_live: bool = False
    enabled_for_paper: bool = True
    tags: list[str] = field(default_factory=list)
    data_provider: str | None = None
    broker_route: str | None = None
    strategy_profile: str | None = None
    base_trade_amount_usd: float | None = None
    max_position_usd: float | None = None
    weekly_budget_multiplier: float | None = None
    allow_force_buy_last_bar: bool = True
    allow_fractional: bool = False

    def __post_init__(self) -> None:
        ensure_non_empty_string(self.symbol, "symbol")
        ensure_non_empty_string(self.market, "market")
        ensure_non_empty_string(self.currency, "currency")
        ensure_non_empty_string(self.timezone, "timezone")
        if self.asset_type not in {"stock", "etf"}:
            raise ValueError("asset_type must be either 'stock' or 'etf'.")

        base_amount = ensure_positive_or_none(self.base_trade_amount_usd, "base_trade_amount_usd")
        max_position = ensure_positive_or_none(self.max_position_usd, "max_position_usd")
        weekly_multiplier = ensure_positive_or_none(self.weekly_budget_multiplier, "weekly_budget_multiplier")

        if base_amount is not None and max_position is not None and max_position < base_amount:
            raise ValueError("max_position_usd must be greater than or equal to base_trade_amount_usd.")
        if weekly_multiplier is not None and weekly_multiplier < 1:
            raise ValueError("weekly_budget_multiplier must be greater than or equal to 1.")

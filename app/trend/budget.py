from __future__ import annotations

from app.account.models import AccountSnapshot, Position
from app.symbols.models import SymbolInfo
from app.trend.models import TrendDecision

MIN_TRADE_AMOUNT_USD = 50.0


def compute_allowed_cash_today(
    symbol: SymbolInfo,
    account: AccountSnapshot,
    position: Position | None,
    recent_trade_stats: dict,
    decision: TrendDecision,
) -> dict[str, float | str]:
    daily_base_budget = float(symbol.base_trade_amount_usd or 0.0)
    weekly_total_budget = daily_base_budget * float(symbol.weekly_budget_multiplier or 1.0)

    weekly_spent = float(recent_trade_stats.get("buy_amount_week", 0.0))
    remaining_weekly_budget = max(0.0, weekly_total_budget - weekly_spent)

    current_market_value = position.market_value if position else 0.0
    max_position = float(symbol.max_position_usd or daily_base_budget)
    remaining_position_capacity = max(0.0, max_position - current_market_value)

    cash_limit = max(0.0, float(account.cash_available))

    allowed_cash_today = min(daily_base_budget, remaining_weekly_budget, remaining_position_capacity, cash_limit)
    planned_amount_usd = max(0.0, allowed_cash_today * float(decision.budget_multiplier))
    final_amount_usd = min(planned_amount_usd, remaining_weekly_budget, remaining_position_capacity, cash_limit)

    reason = "ok"
    if final_amount_usd < MIN_TRADE_AMOUNT_USD:
        reason = "below_min_trade_amount"
        final_amount_usd = 0.0

    return {
        "allowed_cash_today": allowed_cash_today,
        "planned_amount_usd": planned_amount_usd,
        "final_amount_usd": final_amount_usd,
        "reason": reason,
    }

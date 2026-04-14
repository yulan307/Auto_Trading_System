from __future__ import annotations

from datetime import date

from app.trend.budget import compute_allowed_cash_today
from app.trend.models import DailySignal, TrendDecision


def compute_trade_amount(*, symbol, account, position, recent_trade_stats, decision):
    return compute_allowed_cash_today(symbol, account, position, recent_trade_stats, decision)


def generate_daily_signal(
    *,
    trade_date: date,
    ticker: str,
    daily_open: float,
    daily_close: float,
    trend_decision: TrendDecision,
    symbol,
    account,
    position,
    recent_trade_stats,
) -> DailySignal:
    budget = compute_allowed_cash_today(symbol, account, position, recent_trade_stats, trend_decision)

    can_buy = (
        trend_decision.action_bias == "buy_bias"
        and trend_decision.buy_threshold_pct is not None
        and trend_decision.rebound_pct is not None
        and budget["final_amount_usd"] > 0
    )

    if not can_buy:
        can_sell = (
            trend_decision.sell_threshold_pct is not None
            and position is not None
            and position.quantity > 0
        )
        if can_sell:
            base_price = max(float(daily_open), float(daily_close))
            target_price = base_price * (1 + float(trend_decision.sell_threshold_pct))
            estimated_proceeds = float(position.quantity * position.market_price)
            return DailySignal(
                trade_date=trade_date,
                ticker=ticker,
                action="sell",
                target_price=target_price,
                planned_amount_usd=estimated_proceeds,
                allowed_cash_today=0.0,
                final_amount_usd=estimated_proceeds,
                reason=f"sell:{trend_decision.trend_type}",
            )
        return DailySignal(
            trade_date=trade_date,
            ticker=ticker,
            action="hold",
            target_price=None,
            planned_amount_usd=float(budget["planned_amount_usd"]),
            allowed_cash_today=float(budget["allowed_cash_today"]),
            final_amount_usd=float(budget["final_amount_usd"]),
            reason=f"hold:{budget['reason']}",
        )

    base_price = min(float(daily_open), float(daily_close))
    target_price = base_price * (1 - float(trend_decision.buy_threshold_pct))
    if target_price <= 0:
        return DailySignal(
            trade_date=trade_date,
            ticker=ticker,
            action="hold",
            target_price=None,
            planned_amount_usd=float(budget["planned_amount_usd"]),
            allowed_cash_today=float(budget["allowed_cash_today"]),
            final_amount_usd=0.0,
            reason="hold:invalid_target_price",
        )

    return DailySignal(
        trade_date=trade_date,
        ticker=ticker,
        action="buy",
        target_price=target_price,
        planned_amount_usd=float(budget["planned_amount_usd"]),
        allowed_cash_today=float(budget["allowed_cash_today"]),
        final_amount_usd=float(budget["final_amount_usd"]),
        reason=f"buy:{trend_decision.trend_type}",
    )

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

from app.trend.budget import compute_allowed_cash_today
from app.trend.models import DailySignal, StrengthSignal, TrendDecision


DEFAULT_BUY_THRESHOLD_PCT = 0.005
DEFAULT_REBOUND_PCT = 0.003
MIN_STRENGTH_PCT = 0.8
MAX_STRENGTH_PCT = 1.0
MIN_BUY_STRENGTH = 0.5
MAX_BUY_STRENGTH = 1.5


def _coerce_feature_value(feature: Any, key: str) -> float | None:
    if feature is None:
        return None
    if hasattr(feature, "get"):
        value = feature.get(key)
    else:
        try:
            value = feature[key]
        except (KeyError, IndexError, TypeError):
            return None
    if value is None:
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    if numeric_value != numeric_value:
        return None
    return numeric_value


def _map_strength_pct_to_buy_strength(strength_pct: float) -> float:
    clipped = min(max(float(strength_pct), MIN_STRENGTH_PCT), MAX_STRENGTH_PCT)
    pct_span = MAX_STRENGTH_PCT - MIN_STRENGTH_PCT
    strength_span = MAX_BUY_STRENGTH - MIN_BUY_STRENGTH
    if pct_span <= 0:
        return MIN_BUY_STRENGTH
    return MIN_BUY_STRENGTH + ((clipped - MIN_STRENGTH_PCT) / pct_span) * strength_span


def generate_trend_signal(
    *,
    trade_date: date,
    ticker: str,
    feature=None,
) -> TrendDecision:
    return TrendDecision(
        trade_date=trade_date,
        ticker=ticker,
        trend_type="ml_placeholder",
        trend_strength=1.0,
        action_bias="buy_bias",
        buy_threshold_pct=DEFAULT_BUY_THRESHOLD_PCT,
        sell_threshold_pct=None,
        rebound_pct=DEFAULT_REBOUND_PCT,
        budget_multiplier=1.0,
        reason="placeholder_default_buy",
    )


def generate_strength_signal(
    *,
    trade_date: date,
    ticker: str,
    feature,
    buy_strength_pct: float,
    buy_dev_pct: float = 1.0,
) -> StrengthSignal:
    hist_low = _coerce_feature_value(feature, "hist_low")
    buy_activate_price = None if hist_low is None else hist_low * float(buy_dev_pct)
    return StrengthSignal(
        trade_date=trade_date,
        ticker=ticker,
        strength_pct=float(buy_strength_pct),
        buy_strength=_map_strength_pct_to_buy_strength(float(buy_strength_pct)),
        buy_dev_pct=float(buy_dev_pct),
        buy_activate_price=buy_activate_price,
        reason="ml_strength_signal",
    )


def compute_trade_amount(*, symbol, account, position, recent_trade_stats, decision, strength_signal: StrengthSignal | None = None):
    effective_decision = decision
    if strength_signal is not None:
        effective_decision = replace(
            decision,
            budget_multiplier=float(decision.budget_multiplier) * float(strength_signal.buy_strength),
        )
    return compute_allowed_cash_today(symbol, account, position, recent_trade_stats, effective_decision)


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
    strength_signal: StrengthSignal | None = None,
) -> DailySignal:
    budget = compute_trade_amount(
        symbol=symbol,
        account=account,
        position=position,
        recent_trade_stats=recent_trade_stats,
        decision=trend_decision,
        strength_signal=strength_signal,
    )

    can_buy = (
        trend_decision.action_bias == "buy_bias"
        and trend_decision.rebound_pct is not None
        and (
            strength_signal is not None
            or trend_decision.buy_threshold_pct is not None
        )
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

    if strength_signal is not None:
        target_price = strength_signal.buy_activate_price
    else:
        base_price = min(float(daily_open), float(daily_close))
        target_price = base_price * (1 - float(trend_decision.buy_threshold_pct))
    if target_price is None or target_price <= 0:
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

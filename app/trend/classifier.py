from __future__ import annotations

from app.trend.models import TrendDecision, TrendFeatures


def classify_trend(features: TrendFeatures) -> TrendDecision:
    order_code = features.ma_order_code
    slope_code = features.slope_code

    trend_type = "range"
    action_bias = "hold_bias"
    buy_threshold_pct = None
    rebound_pct = None
    budget_multiplier = 0.0

    if order_code == "5>20>60" and slope_code.startswith("++"):
        trend_type = "strong_uptrend"
        action_bias = "buy_bias"
        buy_threshold_pct = 0.005
        rebound_pct = 0.002
        budget_multiplier = 1.2
    elif order_code in {"5>20>60", "20>5>60"} and slope_code[0] in {"+", "0"}:
        trend_type = "weak_uptrend"
        action_bias = "buy_bias"
        buy_threshold_pct = 0.008
        rebound_pct = 0.003
        budget_multiplier = 1.0
    elif order_code in {"20>60>5", "60>20>5"} and slope_code.endswith("--"):
        trend_type = "strong_downtrend"
    elif slope_code == "-0-":
        trend_type = "weak_downtrend"
    elif order_code in {"20>60>5", "60>20>5"} and slope_code[0] == "+":
        trend_type = "rebound_setup"
        action_bias = "buy_bias"
        buy_threshold_pct = 0.01
        rebound_pct = 0.004
        budget_multiplier = 0.8

    strength = abs(features.slope5) * 0.5 + abs(features.slope20) * 0.3 + abs(features.slope60) * 0.2
    return TrendDecision(
        trade_date=features.trade_date,
        ticker=features.ticker,
        trend_type=trend_type,
        trend_strength=strength,
        action_bias=action_bias,
        buy_threshold_pct=buy_threshold_pct,
        sell_threshold_pct=None,
        rebound_pct=rebound_pct,
        budget_multiplier=budget_multiplier,
        reason=f"order={order_code}, slope={slope_code}",
    )

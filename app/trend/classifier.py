from __future__ import annotations

from app.trend.features import MAFeatures
from app.trend.models import TrendDecision

# Thresholds for the trend_rebound_minimal strategy.
# target_price = min(open, close) * (1 - BUY_THRESHOLD_PCT)
BUY_THRESHOLD_PCT = 0.005
REBOUND_PCT = 0.003


def classify_trend(features: MAFeatures) -> TrendDecision:
    """Classify trend from a minimal MA snapshot and return a TrendDecision.

    Uses three-MA ordering (5/20/60) as the sole signal:
      - uptrend   : MA5 > MA20 > MA60  → buy_bias
      - downtrend : MA5 < MA20 < MA60  → hold
      - sideways  : otherwise           → hold
    """
    ma5, ma20, ma60 = features.ma5, features.ma20, features.ma60

    if ma5 > ma20 > ma60:
        return TrendDecision(
            trade_date=features.trade_date,
            ticker=features.ticker,
            trend_type="uptrend",
            trend_strength=1.0,
            action_bias="buy_bias",
            buy_threshold_pct=BUY_THRESHOLD_PCT,
            sell_threshold_pct=None,
            rebound_pct=REBOUND_PCT,
            budget_multiplier=1.0,
            reason="ma5>ma20>ma60",
        )

    if ma5 < ma20 < ma60:
        return TrendDecision(
            trade_date=features.trade_date,
            ticker=features.ticker,
            trend_type="downtrend",
            trend_strength=1.0,
            action_bias="hold",
            buy_threshold_pct=None,
            sell_threshold_pct=None,
            rebound_pct=None,
            budget_multiplier=0.0,
            reason="ma5<ma20<ma60",
        )

    return TrendDecision(
        trade_date=features.trade_date,
        ticker=features.ticker,
        trend_type="sideways",
        trend_strength=0.5,
        action_bias="hold",
        buy_threshold_pct=None,
        sell_threshold_pct=None,
        rebound_pct=None,
        budget_multiplier=0.0,
        reason="mixed_ma_order",
    )

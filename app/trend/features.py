from __future__ import annotations

from datetime import date

from app.trend.models import TrendFeatures


def _ma(values: list[float], window: int) -> float:
    if len(values) < window:
        raise ValueError(f"insufficient data for MA{window}")
    return sum(values[-window:]) / window


def _slope(series: list[float], lookback: int = 3) -> float:
    if len(series) <= lookback:
        raise ValueError("insufficient data for slope calculation")
    base = series[-1 - lookback]
    if base == 0:
        return 0.0
    return (series[-1] - base) / base


def _code_slope(v: float) -> str:
    if v > 0.002:
        return "+"
    if v < -0.002:
        return "-"
    return "0"


def _ma_order(ma5: float, ma20: float, ma60: float) -> str:
    if ma5 > ma20 > ma60:
        return "5>20>60"
    if ma20 > ma5 > ma60:
        return "20>5>60"
    if ma20 > ma60 > ma5:
        return "20>60>5"
    if ma60 > ma20 > ma5:
        return "60>20>5"
    return "mixed"


def compute_ma_features(ticker: str, trade_date: date, closes: list[float], lookback: int = 3) -> TrendFeatures:
    ma5 = _ma(closes, 5)
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)

    ma5_series = [sum(closes[i - 4 : i + 1]) / 5 for i in range(4, len(closes))]
    ma20_series = [sum(closes[i - 19 : i + 1]) / 20 for i in range(19, len(closes))]
    ma60_series = [sum(closes[i - 59 : i + 1]) / 60 for i in range(59, len(closes))]

    slope5 = _slope(ma5_series, lookback=lookback)
    slope20 = _slope(ma20_series, lookback=lookback)
    slope60 = _slope(ma60_series, lookback=lookback)

    return TrendFeatures(
        trade_date=trade_date,
        ticker=ticker,
        close=closes[-1],
        ma5=ma5,
        ma20=ma20,
        ma60=ma60,
        slope5=slope5,
        slope20=slope20,
        slope60=slope60,
        ma_order_code=_ma_order(ma5, ma20, ma60),
        slope_code=f"{_code_slope(slope5)}{_code_slope(slope20)}{_code_slope(slope60)}",
    )

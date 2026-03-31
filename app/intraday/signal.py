from __future__ import annotations


def build_intraday_signal(*, state, bar: dict, daily_signal, rebound_pct: float) -> dict:
    if daily_signal.action != "buy" or daily_signal.target_price is None:
        return {"action": "hold", "reason": "daily_not_buy"}

    tracked_low = state.tracked_low
    close = float(bar["close"])
    target_price = float(daily_signal.target_price)
    if tracked_low is None:
        return {"action": "hold", "reason": "no_tracking_low"}
    if tracked_low > target_price:
        return {"action": "hold", "reason": "target_not_touched"}
    rebound = (close - tracked_low) / tracked_low if tracked_low else 0.0
    if rebound >= rebound_pct:
        limit_price = min(close, target_price)
        return {"action": "place_limit_buy", "limit_price": limit_price, "reason": "rebound_confirmed"}
    return {"action": "hold", "reason": "rebound_not_enough"}

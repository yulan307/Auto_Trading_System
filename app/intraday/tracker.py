from __future__ import annotations

from datetime import datetime

from app.intraday.models import IntradayState


def init_intraday_state(*, ticker: str, trade_date: str, force_trade_enabled: bool) -> IntradayState:
    return IntradayState(
        ticker=ticker,
        trade_date=trade_date,
        tracking_side="buy",
        tracked_low=None,
        tracked_high=None,
        current_order_id=None,
        order_active=False,
        entered_trade=False,
        force_trade_enabled=force_trade_enabled,
        last_bar_time=None,
        note="initialized",
    )


def update_buy_tracking_state(state: IntradayState, bar: dict, *, has_active_order: bool = False) -> IntradayState:
    low = float(bar["low"])
    high = float(bar["high"])
    dt = bar.get("datetime")
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)

    if state.tracked_low is None or low < state.tracked_low:
        state.tracked_low = low
        if has_active_order:
            state.note = "new_low_with_active_order"

    if state.tracked_high is None or high > state.tracked_high:
        state.tracked_high = high

    state.last_bar_time = dt
    return state

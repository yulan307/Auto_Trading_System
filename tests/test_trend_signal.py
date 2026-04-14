from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.account.models import AccountSnapshot
from app.symbols.models import SymbolInfo
from app.trend.models import StrengthSignal
from app.trend.signal import generate_daily_signal, generate_strength_signal, generate_trend_signal


def _build_symbol() -> SymbolInfo:
    return SymbolInfo(
        symbol="SPY",
        market="US",
        asset_type="etf",
        currency="USD",
        timezone="America/New_York",
        base_trade_amount_usd=1000.0,
        max_position_usd=10000.0,
        weekly_budget_multiplier=3.0,
    )


def _build_account() -> AccountSnapshot:
    return AccountSnapshot(
        snapshot_time=datetime.now(timezone.utc),
        mode="backtest",
        account_id="test-account",
        cash_available=10000.0,
        cash_total=10000.0,
        equity_value=0.0,
        market_value=0.0,
        total_asset=10000.0,
    )


def test_generate_trend_signal_returns_placeholder_buy() -> None:
    signal = generate_trend_signal(trade_date=date(2024, 3, 5), ticker="SPY", feature={"hist_low": 100.0})

    assert signal.action_bias == "buy_bias"
    assert signal.buy_threshold_pct == pytest.approx(0.005)
    assert signal.rebound_pct == pytest.approx(0.003)
    assert signal.budget_multiplier == pytest.approx(1.0)
    assert signal.reason == "placeholder_default_buy"


def test_generate_strength_signal_maps_pct_and_builds_activate_price() -> None:
    signal = generate_strength_signal(
        trade_date=date(2024, 3, 5),
        ticker="SPY",
        feature={"hist_low": 80.0},
        buy_strength_pct=0.9,
        buy_dev_pct=1.1,
    )

    assert signal.strength_pct == pytest.approx(0.9)
    assert signal.buy_strength == pytest.approx(1.0)
    assert signal.buy_dev_pct == pytest.approx(1.1)
    assert signal.buy_activate_price == pytest.approx(88.0)


def test_generate_daily_signal_uses_strength_signal_target_and_scaled_budget() -> None:
    trend_signal = generate_trend_signal(trade_date=date(2024, 3, 5), ticker="SPY", feature={"hist_low": 80.0})
    strength_signal = generate_strength_signal(
        trade_date=date(2024, 3, 5),
        ticker="SPY",
        feature={"hist_low": 80.0},
        buy_strength_pct=0.95,
        buy_dev_pct=1.1,
    )

    daily_signal = generate_daily_signal(
        trade_date=date(2024, 3, 5),
        ticker="SPY",
        daily_open=100.0,
        daily_close=102.0,
        trend_decision=trend_signal,
        symbol=_build_symbol(),
        account=_build_account(),
        position=None,
        recent_trade_stats={},
        strength_signal=strength_signal,
    )

    assert daily_signal.action == "buy"
    assert daily_signal.target_price == pytest.approx(88.0)
    assert daily_signal.allowed_cash_today == pytest.approx(1000.0)
    assert daily_signal.planned_amount_usd == pytest.approx(1250.0)
    assert daily_signal.final_amount_usd == pytest.approx(1250.0)


def test_generate_daily_signal_holds_when_strength_signal_has_no_activate_price() -> None:
    trend_signal = generate_trend_signal(trade_date=date(2024, 3, 5), ticker="SPY", feature=None)
    strength_signal = StrengthSignal(
        trade_date=date(2024, 3, 5),
        ticker="SPY",
        strength_pct=0.9,
        buy_strength=1.0,
        buy_dev_pct=1.0,
        buy_activate_price=None,
        reason="missing_hist_low",
    )

    daily_signal = generate_daily_signal(
        trade_date=date(2024, 3, 5),
        ticker="SPY",
        daily_open=100.0,
        daily_close=102.0,
        trend_decision=trend_signal,
        symbol=_build_symbol(),
        account=_build_account(),
        position=None,
        recent_trade_stats={},
        strength_signal=strength_signal,
    )

    assert daily_signal.action == "hold"
    assert daily_signal.target_price is None
    assert daily_signal.reason == "hold:invalid_target_price"

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone
from math import floor
from typing import Any
from uuid import uuid4

from app.account.models import TradeRecord
from app.account.repository import AccountRepository
from app.account.virtual_account import apply_filled_trade, reset_virtual_account
from app.data.repository import load_bars
from app.execution.mock_broker import MockBroker
from app.execution.models import OrderRequest
from app.symbols.models import SymbolInfo
from app.symbols.repository import SymbolRepository
from app.trend.classifier import classify_trend
from app.trend.features import compute_ma_features
from app.trend.signal import generate_daily_signal


MIN_TREND_BARS = 63


def _to_trade_date(value: str) -> date:
    dt = datetime.fromisoformat(value)
    return dt.date()


def _build_default_symbol(ticker: str, runtime_context: dict[str, Any]) -> SymbolInfo:
    timezone_name = runtime_context.get("config", {}).get("timezone", "America/New_York")
    base_amount = float(runtime_context.get("config", {}).get("strategy", {}).get("default_base_trade_amount_usd", 1000.0))
    max_position = float(runtime_context.get("config", {}).get("strategy", {}).get("default_max_position_usd", 3000.0))
    weekly_multiplier = float(runtime_context.get("config", {}).get("strategy", {}).get("default_weekly_budget_multiplier", 3.0))
    return SymbolInfo(
        symbol=ticker,
        market="US",
        asset_type="etf",
        currency="USD",
        timezone=timezone_name,
        enabled_for_backtest=True,
        enabled_for_live=False,
        enabled_for_paper=True,
        tags=["autogen", "minimal_loop"],
        strategy_profile="trend_rebound_minimal",
        base_trade_amount_usd=base_amount,
        max_position_usd=max_position,
        weekly_budget_multiplier=weekly_multiplier,
        allow_force_buy_last_bar=True,
        allow_fractional=bool(runtime_context.get("config", {}).get("execution", {}).get("allow_fractional_default", False)),
    )


def run_backtest(*, ticker: str, start_date, end_date, runtime_context) -> dict:
    config = runtime_context["config"]
    logger = runtime_context["logger"]
    account_repository = AccountRepository(config["data"]["account_db_path"])
    symbol_repository = SymbolRepository(config["data"]["symbols_db_path"])

    snapshot = account_repository.get_account_snapshot()
    if snapshot is None:
        reset_virtual_account(float(config["account"]["initial_cash"]), account_repository, mode="backtest")

    symbol = symbol_repository.get_symbol(ticker) or _build_default_symbol(ticker, runtime_context)

    bars = load_bars(
        config["data"]["daily_db_path"],
        "daily_bars",
        ticker=ticker,
        interval="1d",
        start_date=start_date,
        end_date=end_date,
    )
    if len(bars) < MIN_TREND_BARS:
        return {
            "ticker": ticker,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "mode": runtime_context.get("mode", "backtest"),
            "status": "insufficient_data",
            "required_bars": MIN_TREND_BARS,
            "available_bars": len(bars),
            "trades": [],
            "decisions": [],
            "metrics": {},
        }

    broker = MockBroker()
    decisions: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []

    for idx in range(MIN_TREND_BARS - 1, len(bars)):
        bar = bars[idx]
        trade_date = _to_trade_date(bar["datetime"])
        closes = [float(item["close"]) for item in bars[: idx + 1]]

        features = compute_ma_features(ticker=ticker, trade_date=trade_date, closes=closes)
        decision = classify_trend(features)

        account_snapshot = account_repository.get_account_snapshot()
        if account_snapshot is None:
            raise RuntimeError("virtual account snapshot is missing")
        position = account_repository.get_position(ticker)
        stats = account_repository.get_recent_trade_stats(ticker, trade_date)

        daily_signal = generate_daily_signal(
            trade_date=trade_date,
            ticker=ticker,
            daily_open=float(bar["open"]),
            daily_close=float(bar["close"]),
            trend_decision=decision,
            symbol=symbol,
            account=account_snapshot,
            position=position,
            recent_trade_stats=stats,
        )

        decisions.append(
            {
                "trade_date": trade_date.isoformat(),
                "decision": asdict(decision),
                "signal": asdict(daily_signal),
            }
        )
        logger.log_event(
            level="INFO",
            module="backtest.engine",
            event_type="daily_signal",
            message=daily_signal.reason,
            ticker=ticker,
            payload={
                "trade_date": trade_date.isoformat(),
                "trend_type": decision.trend_type,
                "action": daily_signal.action,
                "target_price": daily_signal.target_price,
                "amount_usd": daily_signal.final_amount_usd,
            },
        )

        if daily_signal.action != "buy" or daily_signal.target_price is None or daily_signal.final_amount_usd <= 0:
            continue
        if float(bar["low"]) > float(daily_signal.target_price):
            continue

        fill_price = float(daily_signal.target_price)
        requested_amount = float(daily_signal.final_amount_usd)
        raw_quantity = requested_amount / fill_price
        allow_fractional = bool(symbol.allow_fractional)
        quantity = raw_quantity if allow_fractional else floor(raw_quantity)
        if quantity <= 0:
            continue
        filled_amount = float(quantity * fill_price)

        order_request = OrderRequest(
            ticker=ticker,
            side="buy",
            order_type="limit",
            price=fill_price,
            amount_usd=filled_amount,
            quantity=quantity,
            reason=daily_signal.reason,
            strategy_tag="trend_rebound_minimal",
        )
        order_status = broker.place_order(order_request)

        trade_time = datetime.combine(trade_date, datetime.min.time(), tzinfo=timezone.utc)
        trade_record = TradeRecord(
            trade_id=f"bt-{uuid4().hex[:12]}",
            order_id=order_status.order_id,
            ticker=ticker,
            side="buy",
            quantity=quantity,
            price=fill_price,
            amount=filled_amount,
            fee=0.0,
            trade_time=trade_time,
            mode="backtest",
            broker="mock",
            note="filled_on_daily_low_touch",
        )
        apply_filled_trade(trade_record, account_repository)

        trades.append(
            {
                "trade_date": trade_date.isoformat(),
                "order_id": order_status.order_id,
                "side": "buy",
                "price": fill_price,
                "quantity": quantity,
                "amount": filled_amount,
                "reason": daily_signal.reason,
            }
        )
        logger.log_event(
            level="INFO",
            module="backtest.engine",
            event_type="order_fill",
            message="mock buy filled",
            ticker=ticker,
            payload=trades[-1],
        )

    final_snapshot = account_repository.get_account_snapshot()
    latest_close = float(bars[-1]["close"])
    final_position = account_repository.get_position(ticker)
    marked_market_value = float(final_position.quantity * latest_close) if final_position else 0.0
    final_cash = float(final_snapshot.cash_available) if final_snapshot else 0.0
    final_asset_estimate = final_cash + marked_market_value
    initial_cash = float(config["account"]["initial_cash"])
    total_return_pct = (final_asset_estimate - initial_cash) / initial_cash if initial_cash > 0 else 0.0

    return {
        "ticker": ticker,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "mode": runtime_context.get("mode", "backtest"),
        "status": "completed",
        "trades": trades,
        "decisions": decisions,
        "metrics": {
            "bars": len(bars),
            "decision_days": len(decisions),
            "buy_trades": len(trades),
            "final_cash": final_cash,
            "marked_market_value": marked_market_value,
            "final_asset_estimate": final_asset_estimate,
            "total_return_pct": total_return_pct,
        },
    }

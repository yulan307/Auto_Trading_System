from __future__ import annotations

from datetime import datetime, timezone

from app.account.models import AccountSnapshot, Position, TradeRecord
from app.account.repository import AccountRepository


_DEFAULT_ACCOUNT_ID = "virtual_default"


def reset_virtual_account(initial_cash: float, repository: AccountRepository, mode: str = "backtest") -> None:
    snapshot = AccountSnapshot(
        snapshot_time=datetime.now(timezone.utc),
        mode=mode,
        account_id=_DEFAULT_ACCOUNT_ID,
        cash_available=float(initial_cash),
        cash_total=float(initial_cash),
        equity_value=0.0,
        market_value=0.0,
        total_asset=float(initial_cash),
    )
    repository.save_account_snapshot(snapshot)


def get_account_snapshot(repository: AccountRepository):
    return repository.get_account_snapshot()


def apply_filled_trade(trade_record: TradeRecord, repository: AccountRepository) -> None:
    snapshot = repository.get_account_snapshot()
    if snapshot is None:
        raise ValueError("virtual account is not initialized")

    position = repository.get_position(trade_record.ticker)
    qty_delta = trade_record.quantity if trade_record.side == "buy" else -trade_record.quantity

    if position is None:
        if qty_delta < 0:
            raise ValueError("cannot sell without existing position")
        new_quantity = qty_delta
        avg_cost = trade_record.price
    else:
        new_quantity = position.quantity + qty_delta
        if new_quantity < 0:
            raise ValueError("sell quantity exceeds current position")
        if trade_record.side == "buy" and new_quantity > 0:
            avg_cost = ((position.quantity * position.avg_cost) + trade_record.amount) / new_quantity
        else:
            avg_cost = position.avg_cost

    if new_quantity > 0:
        repository.upsert_position(
            Position(
                ticker=trade_record.ticker,
                quantity=new_quantity,
                avg_cost=avg_cost,
                market_price=trade_record.price,
                market_value=new_quantity * trade_record.price,
                unrealized_pnl=(trade_record.price - avg_cost) * new_quantity,
            )
        )

    cash_change = -trade_record.amount - trade_record.fee if trade_record.side == "buy" else trade_record.amount - trade_record.fee
    new_cash = snapshot.cash_available + cash_change
    new_market_value = snapshot.market_value + (trade_record.amount if trade_record.side == "buy" else -trade_record.amount)

    repository.save_account_snapshot(
        AccountSnapshot(
            snapshot_time=trade_record.trade_time,
            mode=snapshot.mode,
            account_id=snapshot.account_id,
            cash_available=new_cash,
            cash_total=new_cash,
            equity_value=new_market_value,
            market_value=new_market_value,
            total_asset=new_cash + new_market_value,
        )
    )
    repository.apply_trade(trade_record)

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timedelta

from app.account.models import AccountSnapshot, Position, TradeRecord
from app.data.db import connect_sqlite


class AccountRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def get_account_snapshot(self) -> AccountSnapshot | None:
        with connect_sqlite(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM account_snapshots ORDER BY snapshot_time DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["snapshot_time"] = datetime.fromisoformat(data["snapshot_time"])
        return AccountSnapshot(**data)

    def save_account_snapshot(self, snapshot: AccountSnapshot) -> None:
        data = asdict(snapshot)
        with connect_sqlite(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO account_snapshots(
                    snapshot_time, mode, account_id, cash_available, cash_total,
                    equity_value, market_value, total_asset
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["snapshot_time"].isoformat(),
                    data["mode"],
                    data["account_id"],
                    data["cash_available"],
                    data["cash_total"],
                    data["equity_value"],
                    data["market_value"],
                    data["total_asset"],
                ),
            )

    def get_position(self, ticker: str) -> Position | None:
        with connect_sqlite(self.db_path) as connection:
            row = connection.execute("SELECT * FROM positions WHERE ticker = ?", (ticker,)).fetchone()
        if row is None:
            return None
        return Position(**dict(row))

    def upsert_position(self, position: Position) -> None:
        data = asdict(position)
        with connect_sqlite(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO positions (ticker, quantity, avg_cost, market_price, market_value, unrealized_pnl)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    quantity=excluded.quantity,
                    avg_cost=excluded.avg_cost,
                    market_price=excluded.market_price,
                    market_value=excluded.market_value,
                    unrealized_pnl=excluded.unrealized_pnl
                """,
                (data["ticker"], data["quantity"], data["avg_cost"], data["market_price"], data["market_value"], data["unrealized_pnl"]),
            )

    def apply_trade(self, trade_record: TradeRecord):
        d = asdict(trade_record)
        with connect_sqlite(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO trade_records(
                    trade_id, order_id, ticker, side, quantity, price, amount, fee,
                    trade_time, mode, broker, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    d["trade_id"], d["order_id"], d["ticker"], d["side"], d["quantity"], d["price"], d["amount"], d["fee"],
                    d["trade_time"].isoformat(), d["mode"], d["broker"], d["note"],
                ),
            )

    def delete_position(self, ticker: str) -> None:
        with connect_sqlite(self.db_path) as connection:
            connection.execute("DELETE FROM positions WHERE ticker = ?", (ticker,))

    def clear_for_backtest(self) -> None:
        """Delete all positions and trade records — called at the start of each backtest run."""
        with connect_sqlite(self.db_path) as connection:
            connection.execute("DELETE FROM positions")
            connection.execute("DELETE FROM trade_records")

    def get_recent_trade_stats(self, ticker: str, as_of_date: date) -> dict[str, float]:
        dt_end = datetime.combine(as_of_date, datetime.max.time())
        dt_5d = dt_end - timedelta(days=5)
        week_start = dt_end - timedelta(days=dt_end.weekday())
        with connect_sqlite(self.db_path) as connection:
            rows_5d = connection.execute(
                "SELECT amount FROM trade_records WHERE ticker = ? AND side='buy' AND trade_time >= ? AND trade_time <= ?",
                (ticker, dt_5d.isoformat(), dt_end.isoformat()),
            ).fetchall()
            rows_week = connection.execute(
                "SELECT amount FROM trade_records WHERE ticker = ? AND side='buy' AND trade_time >= ? AND trade_time <= ?",
                (ticker, week_start.isoformat(), dt_end.isoformat()),
            ).fetchall()
        return {
            "buy_amount_5d": float(sum(row["amount"] for row in rows_5d)),
            "buy_amount_week": float(sum(row["amount"] for row in rows_week)),
        }

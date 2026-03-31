from __future__ import annotations

from datetime import date

from app.account.models import TradeRecord
from app.account.repository import AccountRepository


class BaseAccountManager:
    def __init__(self, repository: AccountRepository) -> None:
        self.repository = repository

    def get_account_snapshot(self):
        return self.repository.get_account_snapshot()

    def get_position(self, ticker: str):
        return self.repository.get_position(ticker)

    def get_recent_trade_stats(self, ticker: str, as_of_date: date):
        return self.repository.get_recent_trade_stats(ticker, as_of_date)

    def apply_trade(self, trade_record: TradeRecord):
        self.repository.apply_trade(trade_record)

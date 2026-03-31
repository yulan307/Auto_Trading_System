from __future__ import annotations


class BaseAccountManager:
    def get_account_snapshot(self):
        raise NotImplementedError

    def get_position(self, ticker: str):
        raise NotImplementedError

    def get_recent_trade_stats(self, ticker: str, as_of_date):
        raise NotImplementedError

    def apply_trade(self, trade_record):
        raise NotImplementedError

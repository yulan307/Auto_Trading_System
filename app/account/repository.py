from __future__ import annotations


class AccountRepository:
    def get_account_snapshot(self):
        raise NotImplementedError("AccountRepository will be implemented in phase 3.")

    def get_position(self, ticker: str):
        raise NotImplementedError("AccountRepository will be implemented in phase 3.")

    def apply_trade(self, trade_record):
        raise NotImplementedError("AccountRepository will be implemented in phase 3.")

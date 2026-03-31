from __future__ import annotations


class BaseDataProvider:
    def fetch_bars(self, ticker: str, interval: str, start_date, end_date):
        raise NotImplementedError

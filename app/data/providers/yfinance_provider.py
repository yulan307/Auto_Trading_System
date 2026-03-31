from __future__ import annotations

from app.data.providers.base import BaseDataProvider


class YFinanceProvider(BaseDataProvider):
    def fetch_bars(self, ticker: str, interval: str, start_date, end_date):
        raise NotImplementedError("YFinanceProvider will be implemented in phase 2.")

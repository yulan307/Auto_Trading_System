from __future__ import annotations

from app.data.providers.base import BaseDataProvider


class MoomooProvider(BaseDataProvider):
    def fetch_bars(self, ticker: str, interval: str, start_date, end_date):
        raise NotImplementedError("Moomoo provider is reserved for a later phase.")

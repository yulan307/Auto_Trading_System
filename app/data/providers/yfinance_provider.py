from __future__ import annotations

from datetime import date, datetime

from app.data.providers.base import BaseDataProvider


class YFinanceProvider(BaseDataProvider):
    def fetch_bars(self, ticker: str, interval: str, start_date: date | datetime, end_date: date | datetime):
        try:
            import yfinance as yf
        except ModuleNotFoundError as exc:
            raise RuntimeError("yfinance is not installed. Please install it before fetching remote bars.") from exc

        frame = yf.download(
            tickers=ticker,
            interval=interval,
            start=start_date,
            end=end_date,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if frame is None or frame.empty:
            return []
        frame = frame.reset_index()
        frame = frame.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
                "Date": "datetime",
                "Datetime": "datetime",
            }
        )
        return frame[["datetime", "open", "high", "low", "close", "volume"]].to_dict(orient="records")

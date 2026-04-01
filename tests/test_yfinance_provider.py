from __future__ import annotations

import sys
import types
from datetime import date

import pandas as pd

from app.data.providers.yfinance_provider import YFinanceProvider


def test_fetch_bars_flattens_multiindex_columns(monkeypatch) -> None:
    index = pd.Index([pd.Timestamp("2024-01-02")], name="Date")
    columns = pd.MultiIndex.from_tuples(
        [
            ("Open", "SPY"),
            ("High", "SPY"),
            ("Low", "SPY"),
            ("Close", "SPY"),
            ("Volume", "SPY"),
        ],
        names=["Price", "Ticker"],
    )
    frame = pd.DataFrame(
        [[470.0, 472.0, 469.0, 471.5, 123456789]],
        index=index,
        columns=columns,
    )

    fake_yfinance = types.SimpleNamespace(download=lambda **_: frame)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)

    provider = YFinanceProvider()
    rows = provider.fetch_bars(
        ticker="SPY",
        interval="1d",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 10),
    )

    assert rows == [
        {
            "datetime": pd.Timestamp("2024-01-02"),
            "open": 470.0,
            "high": 472.0,
            "low": 469.0,
            "close": 471.5,
            "volume": 123456789,
        }
    ]

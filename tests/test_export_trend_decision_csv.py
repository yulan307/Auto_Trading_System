from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.export_trend_decision_csv import export_trend_decision_csv


class StubProvider:
    def __init__(self, start: date, end: date) -> None:
        self.start = start
        self.end = end

    def fetch_bars(self, ticker: str, interval: str, start_date: date, end_date: date):
        assert ticker == "SPY"
        assert interval == "1d"
        assert start_date <= self.start
        assert end_date == self.end

        bars = []
        cursor = self.start
        index = 0
        while cursor <= self.end:
            close = 100 + index * 0.2
            bars.append(
                {
                    "datetime": cursor,
                    "open": close - 0.4,
                    "high": close + 0.8,
                    "low": close - 0.8,
                    "close": close,
                    "volume": 1_000_000 + index,
                }
            )
            cursor += timedelta(days=1)
            index += 1
        return bars


def test_export_trend_decision_csv_generates_expected_columns(tmp_path: Path) -> None:
    start_date = date(2025, 7, 1)
    end_date = date(2025, 8, 31)
    provider = StubProvider(start=start_date - timedelta(days=200), end=end_date)

    output_path = export_trend_decision_csv(
        ticker="SPY",
        start_date=start_date,
        end_date=end_date,
        db_path=tmp_path / "daily.db",
        output_dir=tmp_path / "outputs",
        warmup_days=200,
        provider=provider,
        source="stub",
    )

    assert output_path.exists()
    with output_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert all(start_date <= date.fromisoformat(row["trade_date"]) <= end_date for row in rows)
    required_columns = {
        "trade_date",
        "ticker",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ma5",
        "ma20",
        "ma60",
        "slope5",
        "slope20",
        "slope60",
        "ma_order_code",
        "slope_code",
        "trend_type",
        "trend_strength",
        "action_bias",
        "buy_threshold_pct",
        "sell_threshold_pct",
        "rebound_pct",
        "budget_multiplier",
        "reason",
    }
    assert required_columns.issubset(rows[0].keys())


def test_export_trend_decision_csv_raises_when_no_bars_after_update(tmp_path: Path) -> None:
    class EmptyProvider:
        def fetch_bars(self, ticker: str, interval: str, start_date: date, end_date: date):
            return []

    with pytest.raises(RuntimeError, match="No bars found in daily.db after update"):
        export_trend_decision_csv(
            ticker="SPY",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 2, 1),
            db_path=tmp_path / "daily.db",
            output_dir=tmp_path / "outputs",
            provider=EmptyProvider(),
            source="stub",
        )

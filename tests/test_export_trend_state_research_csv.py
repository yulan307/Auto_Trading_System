from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from scripts.export_trend_state_research_csv import (
    build_state_seq_5d,
    encode_ma_state_code,
    encode_slope_state_code,
    export_trend_state_research_csv,
)


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


def test_encode_ma_state_code_covers_all_six_states() -> None:
    assert encode_ma_state_code(ma5=6, ma20=5, ma60=4) == "a"
    assert encode_ma_state_code(ma5=6, ma20=4, ma60=5) == "b"
    assert encode_ma_state_code(ma5=5, ma20=6, ma60=4) == "c"
    assert encode_ma_state_code(ma5=4, ma20=6, ma60=5) == "d"
    assert encode_ma_state_code(ma5=5, ma20=4, ma60=6) == "e"
    assert encode_ma_state_code(ma5=4, ma20=5, ma60=6) == "f"


def test_encode_slope_state_code_covers_all_eight_states() -> None:
    assert encode_slope_state_code(slope5=1.0, slope20=1.0, slope60=1.0) == "1"
    assert encode_slope_state_code(slope5=1.0, slope20=1.0, slope60=0.0) == "2"
    assert encode_slope_state_code(slope5=1.0, slope20=0.0, slope60=1.0) == "3"
    assert encode_slope_state_code(slope5=1.0, slope20=0.0, slope60=0.0) == "4"
    assert encode_slope_state_code(slope5=0.0, slope20=1.0, slope60=1.0) == "5"
    assert encode_slope_state_code(slope5=0.0, slope20=1.0, slope60=0.0) == "6"
    assert encode_slope_state_code(slope5=0.0, slope20=0.0, slope60=1.0) == "7"
    assert encode_slope_state_code(slope5=0.0, slope20=0.0, slope60=0.0) == "8"


def test_build_state_seq_5d_uses_previous_five_days_only() -> None:
    day_state_codes = ["a1", "b1", "c2", "e4", "a1", "d3", "f8"]

    sequences = build_state_seq_5d(day_state_codes)

    assert sequences[:5] == [None, None, None, None, None]
    assert sequences[5] == "a1b1c2e4a1"
    assert sequences[6] == "b1c2e4a1d3"


def test_export_trend_state_research_csv_generates_expected_columns(tmp_path: Path) -> None:
    start_date = date(2025, 7, 1)
    end_date = date(2025, 8, 31)
    provider = StubProvider(start=start_date - timedelta(days=200), end=end_date)
    output_path = tmp_path / "outputs" / "SPY_trend_state_research_1d.csv"

    result_path = export_trend_state_research_csv(
        ticker="SPY",
        start_date=start_date,
        end_date=end_date,
        db_path=tmp_path / "daily.db",
        output_path=output_path,
        warmup_days=200,
        provider=provider,
        source="stub",
    )

    assert result_path == output_path
    assert result_path.exists()

    with result_path.open("r", encoding="utf-8") as handle:
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
        "ma_state_code",
        "slope_state_code",
        "day_state_code",
        "state_seq_5d",
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
    assert all(len(row["slope_state_code"]) == 1 for row in rows)
    assert all(len(row["day_state_code"]) == 2 for row in rows if row["day_state_code"])
    assert any(len(row["state_seq_5d"]) == 10 for row in rows if row["state_seq_5d"])

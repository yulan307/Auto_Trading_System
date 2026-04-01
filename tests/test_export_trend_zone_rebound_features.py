from __future__ import annotations

import codecs
import csv
import math
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from scripts.export_trend_zone_rebound_features import (
    DAILY_FIELDNAMES,
    REBOUND_COMBOS,
    ZONE_COMBOS,
    build_single_ticker_feature_table,
    build_summary_table,
    export_trend_zone_rebound_features,
)


class MultiTickerStubProvider:
    def __init__(self, start: date, end: date) -> None:
        self.start = start
        self.end = end

    def fetch_bars(self, ticker: str, interval: str, start_date: date, end_date: date):
        assert interval == "1d"
        assert start_date <= self.start
        assert end_date == self.end

        bars = []
        cursor = self.start
        index = 0
        while cursor <= self.end:
            if ticker == "SPY":
                close = 100 + index * 0.22 + math.sin(index / 6) * 3.0
            elif ticker == "QQQ":
                close = 180 - index * 0.10 + math.cos(index / 5) * 4.0
            else:
                raise AssertionError(f"unexpected ticker {ticker}")

            bars.append(
                {
                    "datetime": cursor,
                    "open": close - 0.4,
                    "high": close + 1.0,
                    "low": close - 1.2 - (index % 3) * 0.05,
                    "close": close,
                    "volume": 1_000_000 + index * 250 + (50_000 if ticker == "QQQ" else 0),
                }
            )
            cursor += timedelta(days=1)
            index += 1
        return bars


class ShortHistoryProvider:
    def fetch_bars(self, ticker: str, interval: str, start_date: date, end_date: date):
        assert ticker == "IWM"
        assert interval == "1d"

        bars = []
        cursor = start_date
        index = 0
        while cursor <= end_date:
            close = 90 + index * 0.5
            bars.append(
                {
                    "datetime": cursor,
                    "open": close - 0.2,
                    "high": close + 0.6,
                    "low": close - 0.7,
                    "close": close,
                    "volume": 500_000 + index,
                }
            )
            cursor += timedelta(days=1)
            index += 1
        return bars


def test_export_trend_zone_rebound_features_writes_daily_and_summary_csvs(tmp_path: Path) -> None:
    start_date = date(2025, 7, 1)
    end_date = date(2025, 9, 30)
    provider = MultiTickerStubProvider(start=start_date - timedelta(days=220), end=end_date)

    daily_path, summary_path = export_trend_zone_rebound_features(
        tickers=["SPY", "QQQ"],
        start_date=start_date,
        end_date=end_date,
        db_path=tmp_path / "daily.db",
        output_dir=tmp_path / "outputs",
        warmup_days=220,
        provider=provider,
        source="stub",
    )

    assert daily_path.exists()
    assert summary_path.exists()
    assert daily_path.read_bytes().startswith(codecs.BOM_UTF8)
    assert summary_path.read_bytes().startswith(codecs.BOM_UTF8)

    daily_df = pd.read_csv(daily_path, encoding="utf-8-sig")
    summary_df = pd.read_csv(summary_path, encoding="utf-8-sig")

    assert set(daily_df["ticker"]) == {"SPY", "QQQ"}
    assert set(summary_df["ticker"]) == {"SPY", "QQQ"}
    assert set(DAILY_FIELDNAMES).issubset(daily_df.columns)
    assert daily_df["date"].between(start_date.isoformat(), end_date.isoformat()).all()

    non_null_zone = daily_df["zone_combo_3"].dropna()
    assert not non_null_zone.empty
    assert non_null_zone.map(lambda value: value in ZONE_COMBOS or "0" in value).all()

    non_null_rebound = daily_df["rebound_base_combo_2"].dropna()
    assert not non_null_rebound.empty
    assert non_null_rebound.map(lambda value: value in REBOUND_COMBOS or "0" in value).all()

    for ticker in ("SPY", "QQQ"):
        ticker_daily = daily_df[daily_df["ticker"] == ticker]
        valid_daily = ticker_daily[ticker_daily["valid_row_flag"] == 1]
        ticker_summary = summary_df.loc[summary_df["ticker"] == ticker].iloc[0]

        assert int(ticker_summary["row_count"]) == len(ticker_daily)
        assert int(ticker_summary["valid_row_count"]) == len(valid_daily)

        for combo in ZONE_COMBOS:
            assert int(ticker_summary[f"combo_{combo}_count"]) == int((valid_daily["zone_combo_3"] == combo).sum())
        for combo in REBOUND_COMBOS:
            assert int(ticker_summary[f"rebound_combo_{combo}_count"]) == int(
                (valid_daily["rebound_base_combo_2"] == combo).sum()
            )


def test_build_single_ticker_feature_table_keeps_invalid_rows_when_history_is_too_short(tmp_path: Path) -> None:
    start_date = date(2025, 1, 1)
    end_date = date(2025, 1, 30)

    daily_df = build_single_ticker_feature_table(
        ticker="IWM",
        start_date=start_date,
        end_date=end_date,
        db_path=tmp_path / "daily.db",
        warmup_days=0,
        provider=ShortHistoryProvider(),
        source="stub",
    )

    assert len(daily_df) == 30
    assert set(daily_df["valid_row_flag"]) == {0}
    assert daily_df["ma60"].isna().all()
    assert daily_df["zone_combo_3"].isna().all()


def test_build_summary_table_separates_zero_sign_combos_and_ignores_invalid_rows() -> None:
    daily_df = pd.DataFrame(
        [
            {
                "ticker": "SPY",
                "date": "2025-01-01",
                "zone_combo_3": "+++",
                "rebound_base_combo_2": "++",
                "valid_row_flag": 1,
            },
            {
                "ticker": "SPY",
                "date": "2025-01-02",
                "zone_combo_3": "++0",
                "rebound_base_combo_2": "+0",
                "valid_row_flag": 1,
            },
            {
                "ticker": "SPY",
                "date": "2025-01-03",
                "zone_combo_3": "---",
                "rebound_base_combo_2": "--",
                "valid_row_flag": 0,
            },
        ]
    )

    summary_df = build_summary_table(daily_df, start_date=date(2025, 1, 1), end_date=date(2025, 1, 3))
    row = summary_df.iloc[0]

    assert int(row["row_count"]) == 3
    assert int(row["valid_row_count"]) == 2
    assert int(row["combo_+++_count"]) == 1
    assert int(row["combo_---_count"]) == 0
    assert int(row["combo_zero_sign_count"]) == 1
    assert int(row["rebound_combo_++_count"]) == 1
    assert int(row["rebound_combo_--_count"]) == 0
    assert int(row["rebound_combo_zero_sign_count"]) == 1


def test_exported_daily_csv_has_excel_friendly_header(tmp_path: Path) -> None:
    start_date = date(2025, 8, 1)
    end_date = date(2025, 8, 5)
    provider = MultiTickerStubProvider(start=start_date - timedelta(days=220), end=end_date)

    daily_path, _ = export_trend_zone_rebound_features(
        tickers=["SPY"],
        start_date=start_date,
        end_date=end_date,
        db_path=tmp_path / "daily.db",
        output_dir=tmp_path / "outputs",
        warmup_days=220,
        provider=provider,
        source="stub",
    )

    with daily_path.open("r", encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle))

    assert header[:4] == ["ticker", "date", "open", "high"]

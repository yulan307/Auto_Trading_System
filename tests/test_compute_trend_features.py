from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.data.db import connect_sqlite, init_price_db
from app.data.repository import save_bars
from app.trend.features import (
    OUTPUT_COLUMNS,
    _compute_linear_slope,
    compute_fetch_start_date,
    compute_hist_warmup_bars,
    compute_signed_rolling_percentile,
    compute_total_warmup_bars,
    compute_trend_features_for_ticker,
    init_feature_db,
    run_trend_feature_pipeline,
    update_feature_db,
)


def _business_days(start: date, end: date) -> list[date]:
    return [ts.date() for ts in pd.bdate_range(start=start, end=end)]


def _seed_daily_db(
    db_path: Path,
    *,
    ticker: str,
    start: date,
    end: date,
    spike_date: date | None = None,
    close_step: float = 1.0,
) -> list[date]:
    init_price_db(db_path, "daily_bars")

    bars: list[dict[str, object]] = []
    business_days = _business_days(start, end)
    spike_index = business_days.index(spike_date) if spike_date in business_days else None

    for index, current in enumerate(business_days):
        close = 100.0 + index * close_step
        if spike_index is not None and index == spike_index:
            close = 999_999.0

        high = close + 2.0
        low = close - 2.0
        if spike_index is not None and index == spike_index:
            high = 888_888.0
            low = 0.01

        bars.append(
            {
                "ticker": ticker,
                "datetime": current,
                "interval": "1d",
                "open": close - 1.0,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1_000_000.0 + index,
                "source": "seed",
                "update_time": datetime.now(timezone.utc),
            }
        )

    save_bars(db_path, "daily_bars", bars)
    return business_days


def _create_legacy_trend_feature_table(db_path: Path) -> None:
    with connect_sqlite(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS trend_features_daily (
                ticker TEXT NOT NULL,
                datetime TEXT NOT NULL,
                open REAL,
                close REAL,
                PRIMARY KEY (ticker, datetime)
            )
            """
        )


def test_compute_signed_rolling_percentile_separates_positive_negative_zero_and_history_rules() -> None:
    positive_series = pd.Series([1.0, 2.0, 3.0, 2.5])
    negative_series = pd.Series([-1.0, -3.0, -2.0, -2.5])
    mixed_series = pd.Series([1.0, 2.0, 3.0, 0.0, float("nan"), 4.0])

    positive_pct = compute_signed_rolling_percentile(positive_series, history_window=3)
    negative_pct = compute_signed_rolling_percentile(negative_series, history_window=3)
    mixed_pct = compute_signed_rolling_percentile(mixed_series, history_window=3)

    assert positive_pct.iloc[:3].isna().all()
    assert positive_pct.iloc[3] == pytest.approx(2 / 3)
    assert negative_pct.iloc[:3].isna().all()
    assert negative_pct.iloc[3] == pytest.approx(-2 / 3)
    assert mixed_pct.iloc[3] == 0.0
    assert pd.isna(mixed_pct.iloc[4])
    assert pd.isna(mixed_pct.iloc[5])


def test_warmup_definition_matches_hist_plus_pct_requirement() -> None:
    assert compute_hist_warmup_bars() == 239
    assert compute_total_warmup_bars() == 495
    expected = (date(2024, 1, 1) - timedelta(days=724)).isoformat()
    assert compute_fetch_start_date("2024-01-01") == expected


def test_compute_trend_features_for_ticker_uses_hist_and_fut_time_semantics(tmp_path: Path) -> None:
    db_path = tmp_path / "daily.db"
    seed_start = date(2022, 1, 3)
    start_date = date(2024, 1, 2)
    end_date = date(2024, 7, 31)
    spike_date = date(2024, 3, 1)

    business_days = _seed_daily_db(
        db_path,
        ticker="SPY",
        start=seed_start,
        end=end_date,
        spike_date=spike_date,
    )
    spike_index = business_days.index(spike_date)

    feature_df = compute_trend_features_for_ticker(
        ticker="SPY",
        start_date=start_date,
        end_date=end_date,
        daily_db_path=db_path,
        history_window=30,
    )

    spike_row = feature_df.loc[feature_df["datetime"] == spike_date.isoformat()].iloc[0]

    expected_hist_close = 100.0 + (spike_index - 1)
    expected_hist_low = expected_hist_close - 2.0
    expected_hist_high = expected_hist_close + 2.0
    expected_hist_ma_w = np.mean([100.0 + offset for offset in range(spike_index - 5, spike_index)])

    fut_window_values = np.array(
        [
            100.0 + offset if offset != spike_index else 999_999.0
            for offset in range(spike_index - 2, spike_index + 3)
        ],
        dtype=float,
    )
    expected_fut_ma_w = float(fut_window_values.mean())
    expected_fut_slope_w = _compute_linear_slope(fut_window_values)
    expected_fut_low_dev_w = 0.01 / expected_fut_ma_w - 1.0

    assert spike_row["hist_close"] == pytest.approx(expected_hist_close)
    assert spike_row["hist_low"] == pytest.approx(expected_hist_low)
    assert spike_row["hist_high"] == pytest.approx(expected_hist_high)
    assert spike_row["hist_ma_w"] == pytest.approx(expected_hist_ma_w)
    assert spike_row["fut_ma_w"] == pytest.approx(expected_fut_ma_w)
    assert spike_row["fut_slope_w"] == pytest.approx(expected_fut_slope_w)
    assert spike_row["fut_low_dev_w"] == pytest.approx(expected_fut_low_dev_w)


def test_run_trend_feature_pipeline_writes_new_outputs_and_migrates_legacy_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "daily.db"
    output_sqlite_path = tmp_path / "processed" / "trend_features.db"
    output_csv_dir = tmp_path / "processed" / "features"
    seed_start = date(2022, 1, 3)
    start_date = date(2024, 1, 2)
    end_date = date(2024, 3, 29)

    _seed_daily_db(db_path, ticker="SPY", start=seed_start, end=end_date, close_step=1.0)
    _seed_daily_db(db_path, ticker="QQQ", start=seed_start, end=end_date, close_step=0.5)
    _create_legacy_trend_feature_table(output_sqlite_path)

    result = run_trend_feature_pipeline(
        tickers=["SPY", "QQQ"],
        start_date=start_date,
        end_date=end_date,
        daily_db_path=db_path,
        output_sqlite_path=output_sqlite_path,
        output_csv_dir=output_csv_dir,
        history_window=30,
    )

    assert result.failed_tickers == []
    assert len(result.csv_paths) == 2
    assert output_sqlite_path.exists()

    spy_csv = pd.read_csv(output_csv_dir / "SPY_trend_features.csv", encoding="utf-8-sig")
    assert set(spy_csv["ticker"]) == {"SPY"}
    assert spy_csv["datetime"].between(start_date.isoformat(), end_date.isoformat()).all()
    assert set(OUTPUT_COLUMNS).issubset(spy_csv.columns)
    assert {"interval", "source", "update_time", "hist_open", "fut_ma_w"}.issubset(spy_csv.columns)

    with connect_sqlite(output_sqlite_path) as connection:
        row_count = connection.execute("SELECT COUNT(*) AS cnt FROM trend_features_daily").fetchone()["cnt"]
        sqlite_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(trend_features_daily)").fetchall()
        }

    assert row_count == len(result.combined_df)
    assert row_count == result.sqlite_rows_written
    assert set(OUTPUT_COLUMNS).issubset(sqlite_columns)


def test_init_feature_db_creates_table_and_adds_missing_columns(tmp_path: Path) -> None:
    feature_db_path = tmp_path / "feature.db"
    _create_legacy_trend_feature_table(feature_db_path)

    init_feature_db(feature_db_path=feature_db_path)

    with connect_sqlite(feature_db_path) as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(trend_features_daily)").fetchall()}

    assert set(OUTPUT_COLUMNS).issubset(columns)


def test_update_feature_db_writes_only_available_trade_dates(tmp_path: Path) -> None:
    daily_db_path = tmp_path / "daily.db"
    feature_db_path = tmp_path / "feature.db"
    seed_start = date(2022, 1, 3)
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 10)

    business_days = _seed_daily_db(daily_db_path, ticker="SPY", start=seed_start, end=end_date)
    expected_dates = [d.isoformat() for d in business_days if start_date <= d <= end_date]

    assert update_feature_db(
        "SPY",
        start_date,
        end_date,
        daily_db_path=daily_db_path,
        feature_db_path=feature_db_path,
        history_window=30,
    )

    with connect_sqlite(feature_db_path) as connection:
        rows = connection.execute(
            """
            SELECT datetime
            FROM trend_features_daily
            WHERE ticker = 'SPY'
            ORDER BY datetime ASC
            """
        ).fetchall()

    assert [row["datetime"] for row in rows] == expected_dates
    assert "2024-01-06" not in expected_dates
    assert "2024-01-07" not in expected_dates


def test_update_feature_db_uses_yfinance_updater_when_daily_history_is_insufficient(tmp_path: Path, monkeypatch) -> None:
    daily_db_path = tmp_path / "daily.db"
    feature_db_path = tmp_path / "feature.db"
    start_date = date(2024, 1, 2)
    end_date = date(2024, 1, 31)

    _seed_daily_db(daily_db_path, ticker="SPY", start=start_date, end=end_date)
    calls: list[tuple[date, date]] = []

    def _fake_update_symbol_data(*, provider, db_path, ticker, interval, start_date, end_date, source):
        calls.append((start_date, end_date))
        _seed_daily_db(Path(db_path), ticker=ticker, start=date(2022, 1, 3), end=end_date)
        return {"saved": 1}

    monkeypatch.setattr("app.trend.features.update_symbol_data", _fake_update_symbol_data)

    result = update_feature_db(
        "SPY",
        start_date,
        end_date,
        daily_db_path=daily_db_path,
        feature_db_path=feature_db_path,
        history_window=30,
    )

    assert result is True
    assert calls


def test_update_feature_db_backfills_recent_rows_when_future_window_matures(tmp_path: Path) -> None:
    daily_db_path = tmp_path / "daily.db"
    feature_db_path = tmp_path / "feature.db"
    full_start = date(2022, 1, 3)
    first_end = date(2024, 1, 5)
    second_end = date(2024, 1, 19)

    _seed_daily_db(daily_db_path, ticker="SPY", start=full_start, end=first_end)
    assert update_feature_db(
        "SPY",
        date(2024, 1, 1),
        first_end,
        daily_db_path=daily_db_path,
        feature_db_path=feature_db_path,
        history_window=30,
    )

    with connect_sqlite(feature_db_path) as connection:
        initial_value = connection.execute(
            """
            SELECT fut_ma_m
            FROM trend_features_daily
            WHERE ticker = 'SPY' AND datetime = '2024-01-05'
            """
        ).fetchone()["fut_ma_m"]

    assert initial_value is None

    _seed_daily_db(daily_db_path, ticker="SPY", start=full_start, end=second_end)
    assert update_feature_db(
        "SPY",
        date(2024, 1, 8),
        second_end,
        daily_db_path=daily_db_path,
        feature_db_path=feature_db_path,
        history_window=30,
    )

    with connect_sqlite(feature_db_path) as connection:
        matured_value = connection.execute(
            """
            SELECT fut_ma_m
            FROM trend_features_daily
            WHERE ticker = 'SPY' AND datetime = '2024-01-05'
            """
        ).fetchone()["fut_ma_m"]

    assert matured_value is not None

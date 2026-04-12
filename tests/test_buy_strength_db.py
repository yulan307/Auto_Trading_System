from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from app.data.db import connect_sqlite
from app.ml.buy_strength_label.init_db import init_buy_strength_db
from app.ml.buy_strength_label.repository import load_strength_rows
from app.ml.buy_strength_label.updater import update_buy_strength_db
from app.trend.features import OUTPUT_COLUMNS, init_feature_db, save_features_to_sqlite


def _build_feature_rows(ticker: str, start_date: str, periods: int = 8) -> pd.DataFrame:
    base_date = pd.Timestamp(start_date)
    rows: list[dict[str, object]] = []
    hist_columns = [column for column in OUTPUT_COLUMNS if column.startswith("hist_")]
    for index in range(periods):
        row: dict[str, object] = {column: None for column in OUTPUT_COLUMNS}
        current_date = (base_date + timedelta(days=index)).date().isoformat()
        row.update(
            {
                "ticker": ticker,
                "datetime": current_date,
                "interval": "1d",
                "open": 100.0 + index,
                "high": 101.0 + index,
                "low": 99.0 + index,
                "close": 100.5 + index,
                "volume": 1000.0 + index,
                "source": "test",
                "update_time": datetime.now(timezone.utc).isoformat(),
                "fut_low_dev_w": -0.01 * (index + 1),
                "fut_low_dev_m": -0.005 * (index + 1),
                "fut_low_dev_drv2_w": 1.0 + index * 0.1,
            }
        )
        for hist_col_index, column in enumerate(hist_columns, start=1):
            row[column] = float(index + hist_col_index)
        rows.append(row)
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def test_init_buy_strength_db_creates_table(tmp_path):
    db_path = tmp_path / "buy_strength.db"

    init_buy_strength_db(str(db_path))

    with connect_sqlite(db_path) as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert "buy_strength_daily" in tables


def test_update_buy_strength_db_writes_and_skips_existing_rows(tmp_path, monkeypatch):
    feature_db_path = tmp_path / "feature.db"
    strength_db_path = tmp_path / "buy_strength.db"
    init_feature_db(feature_db_path=feature_db_path)
    save_features_to_sqlite(_build_feature_rows("SPY", "2024-01-01"), sqlite_path=feature_db_path)

    monkeypatch.setattr("app.ml.buy_strength_label.updater.update_feature_db", lambda **_: True)

    first_result = update_buy_strength_db(
        ticker="SPY",
        start_date="2024-01-01",
        end_date="2024-01-08",
        feature_db_path=str(feature_db_path),
        strength_db_path=str(strength_db_path),
    )
    second_result = update_buy_strength_db(
        ticker="SPY",
        start_date="2024-01-01",
        end_date="2024-01-08",
        feature_db_path=str(feature_db_path),
        strength_db_path=str(strength_db_path),
    )
    stored = load_strength_rows(
        tickers="SPY",
        start_date="2024-01-01",
        end_date="2024-01-08",
        db_path=str(strength_db_path),
    )

    assert first_result["new_rows"] == 8
    assert second_result["new_rows"] == 0
    assert second_result["existing_rows"] == 8
    assert len(stored) == 8
    assert set(stored.columns) == {"ticker", "date", "strength", "label_version", "update_time"}

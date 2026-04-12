from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from app.ml.buy_strength_label.strength_pct import get_strength_pct_frame
from app.trend.features import OUTPUT_COLUMNS, init_feature_db, save_features_to_sqlite


def _seed_feature_db(feature_db_path, ticker: str, start_date: str, periods: int = 10) -> None:
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
                "open": 50.0 + index,
                "high": 51.0 + index,
                "low": 49.0 + index,
                "close": 50.5 + index,
                "volume": 100.0 + index,
                "source": "test",
                "update_time": datetime.now(timezone.utc).isoformat(),
                "fut_low_dev_w": -0.02 * (index + 1),
                "fut_low_dev_m": -0.01 * (index + 1),
                "fut_low_dev_drv2_w": 0.5 + index * 0.05,
            }
        )
        for hist_col_index, column in enumerate(hist_columns, start=1):
            row[column] = float(index + hist_col_index) / 10.0
        rows.append(row)
    save_features_to_sqlite(pd.DataFrame(rows, columns=OUTPUT_COLUMNS), sqlite_path=feature_db_path)


def test_get_strength_pct_frame_returns_expected_columns_and_supports_multi_ticker(tmp_path, monkeypatch):
    feature_db_path = tmp_path / "feature.db"
    strength_db_path = tmp_path / "buy_strength.db"
    init_feature_db(feature_db_path=feature_db_path)
    _seed_feature_db(feature_db_path, "SPY", "2024-01-01")
    _seed_feature_db(feature_db_path, "QQQ", "2024-01-01")

    monkeypatch.setattr("app.ml.buy_strength_label.updater.update_feature_db", lambda **_: True)

    frame = get_strength_pct_frame(
        tickers=["SPY", "QQQ"],
        end_date="2024-01-10",
        strength_pct_length_month=1,
        feature_db_path=str(feature_db_path),
        strength_db_path=str(strength_db_path),
    )

    assert not frame.empty
    assert {"ticker", "date", "strength", "label_version", "strength_pct"} <= set(frame.columns)
    assert set(frame["ticker"]) == {"SPY", "QQQ"}

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from app.ml.buy_sub_ml.dataset import build_buy_sub_ml_dataset
from app.trend.features import OUTPUT_COLUMNS, init_feature_db, save_features_to_sqlite


def _insert_feature_rows(feature_db_path, ticker: str, start_date: str, periods: int = 12) -> None:
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
                "open": 200.0 + index,
                "high": 201.0 + index,
                "low": 199.0 + index,
                "close": 200.5 + index,
                "volume": 1000.0 + index,
                "source": "test",
                "update_time": datetime.now(timezone.utc).isoformat(),
                "fut_low_dev_w": -0.015 * (index + 1),
                "fut_low_dev_m": -0.0075 * (index + 1),
                "fut_low_dev_drv2_w": 0.8 + index * 0.04,
            }
        )
        for hist_col_index, column in enumerate(hist_columns, start=1):
            row[column] = float(index + hist_col_index)
        rows.append(row)
    save_features_to_sqlite(pd.DataFrame(rows, columns=OUTPUT_COLUMNS), sqlite_path=feature_db_path)


def test_build_buy_sub_ml_dataset_only_contains_hist_inputs_and_strength_pct(tmp_path, monkeypatch):
    feature_db_path = tmp_path / "feature.db"
    strength_db_path = tmp_path / "buy_strength.db"
    init_feature_db(feature_db_path=feature_db_path)
    _insert_feature_rows(feature_db_path, "SPY", "2024-02-01")

    monkeypatch.setattr("app.ml.buy_strength_label.updater.update_feature_db", lambda **_: True)
    monkeypatch.setattr("app.ml.buy_sub_ml.dataset.update_feature_db", lambda **_: True)

    dataset = build_buy_sub_ml_dataset(
        tickers=["SPY"],
        end_date="2024-02-12",
        strength_pct_length_month=1,
        feature_db_path=str(feature_db_path),
        strength_db_path=str(strength_db_path),
    )

    feature_columns = [column for column in dataset.columns if column not in {"ticker", "date", "strength", "strength_pct"}]
    assert not dataset.empty
    assert feature_columns
    assert all(column.startswith("hist_") for column in feature_columns)
    assert "strength" in dataset.columns
    assert "strength_pct" in dataset.columns

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from app.ml.buy_sub_ml.artifact import save_experiment_artifacts
from app.ml.buy_sub_ml.inference import infer_buy_strength_pct, infer_buy_strength_signal_inputs
from app.ml.buy_sub_ml.registry import promote_buy_model
from app.ml.buy_sub_ml.trainer import StandardScalerState
from app.data.db import init_price_db
from app.data.repository import save_bars
from app.trend.features import OUTPUT_COLUMNS, init_feature_db, save_features_to_sqlite


def _seed_rows(feature_db_path, ticker: str, start_date: str, periods: int = 6) -> None:
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
                "open": 80.0 + index,
                "high": 81.0 + index,
                "low": 79.0 + index,
                "close": 80.5 + index,
                "volume": 200.0 + index,
                "source": "test",
                "update_time": datetime.now(timezone.utc).isoformat(),
                "fut_low_dev_w": -0.01 * (index + 1),
                "fut_low_dev_m": -0.005 * (index + 1),
                "fut_low_dev_drv2_w": 1.2 + index * 0.05,
            }
        )
        for hist_col_index, column in enumerate(hist_columns, start=1):
            row[column] = float(index + hist_col_index) / 5.0
        rows.append(row)
    save_features_to_sqlite(pd.DataFrame(rows, columns=OUTPUT_COLUMNS), sqlite_path=feature_db_path)


def _write_runtime_config(tmp_path: Path, *, daily_db_path: Path, model_version: str = "buy/v001") -> Path:
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        "\n".join(
            [
                "mode: backtest",
                "timezone: UTC",
                "data:",
                f"  daily_db_path: {daily_db_path.as_posix()}",
                "  feature_db_path: data/feature.db",
                "  intraday_db_path: data/intraday.db",
                "  symbols_db_path: data/symbols.db",
                "  account_db_path: data/account.db",
                "  logs_db_path: data/logs.db",
                "account:",
                "  account_source: local_virtual",
                "  initial_cash: 100000",
                "execution:",
                "  broker: mock",
                "  allow_fractional_default: false",
                "logging:",
                "  log_level: INFO",
                "  log_dir: logs",
                "strategy:",
                "  ma_windows: [5, 20, 60]",
                "  intraday_interval: 15m",
                "  last_bar_force_trade: true",
                "ml:",
                "  enabled: true",
                f"  buy_model_version: {model_version}",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def _seed_daily_bars(daily_db_path: Path, *, ticker: str, rows: list[tuple[str, float, float, float, float]]) -> None:
    init_price_db(daily_db_path, "daily_bars")
    bars: list[dict[str, object]] = []
    for date_str, open_price, high_price, low_price, close_price in rows:
        bars.append(
            {
                "ticker": ticker,
                "datetime": date_str,
                "interval": "1d",
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": 1_000_000.0,
                "source": "seed",
                "update_time": datetime.now(timezone.utc).isoformat(),
            }
        )
    save_bars(daily_db_path, "daily_bars", bars)


def test_infer_buy_strength_pct_writes_csv_with_expected_name(tmp_path, monkeypatch):
    feature_db_path = tmp_path / "feature.db"
    strength_db_path = tmp_path / "buy_strength.db"
    output_dir = tmp_path / "outputs"
    artifact_dir = tmp_path / "artifacts"
    model_root = tmp_path / "models" / "buy"
    init_feature_db(feature_db_path=feature_db_path)
    _seed_rows(feature_db_path, "SPY", "2024-03-01")

    feature_columns = ["hist_open", "hist_close"]
    save_experiment_artifacts(
        artifact_dir=str(artifact_dir),
        model={"backend": "numpy_fallback", "weights": [0.3, 0.7], "bias": 0.1},
        scaler=StandardScalerState(mean_=[0.0, 0.0], scale_=[1.0, 1.0], feature_columns=feature_columns),
        feature_columns=feature_columns,
        train_config={"resolved_backend": "numpy_fallback"},
        metrics={"overall": {"rmse": 0.0}},
        predictions_df=pd.DataFrame(
            {"ticker": ["SPY"], "date": ["2024-03-01"], "strength_pct": [0.5], "pred_strength_pct": [0.5]}
        ),
    )
    promote_buy_model(
        artifact_dir=str(artifact_dir),
        model_version="buy/v001",
        model_root=str(model_root),
        registry_path=str(model_root / "registry.json"),
    )

    monkeypatch.setattr("app.ml.buy_strength_label.updater.update_feature_db", lambda **_: True)
    monkeypatch.setattr("app.ml.buy_sub_ml.inference.update_feature_db", lambda **_: True)

    output_path = infer_buy_strength_pct(
        tickers=["SPY"],
        start_date="2024-03-03",
        end_date="2024-03-06",
        strength_pct_length_month=1,
        model_version="buy/v001",
        feature_db_path=str(feature_db_path),
        strength_db_path=str(strength_db_path),
        model_root=str(model_root),
        output_dir=str(output_dir),
    )

    output_file = pd.read_csv(output_path)
    assert output_path.endswith("SPY_2024-03-06_buy_v001_strength_pct_pred.csv")
    assert output_file["date"].min() >= "2024-03-03"
    assert output_file["date"].max() <= "2024-03-06"
    assert {
        "ticker",
        "date",
        "hist_open",
        "hist_close",
        "strength",
        "strength_pct",
        "pred_strength_pct",
        "model_version",
    } <= set(output_file.columns)


def test_infer_buy_strength_signal_inputs_uses_actual_trade_day_bar(tmp_path, monkeypatch):
    daily_db_path = tmp_path / "daily.db"
    config_path = _write_runtime_config(tmp_path, daily_db_path=daily_db_path)
    artifact_dir = tmp_path / "artifacts"
    model_root = tmp_path / "models" / "buy"
    _seed_daily_bars(
        daily_db_path,
        ticker="SPY",
        rows=[
            ("2024-03-01", 100.0, 101.0, 99.0, 100.5),
            ("2024-03-04", 101.0, 102.0, 100.0, 101.5),
            ("2024-03-05", 102.0, 103.0, 101.0, 102.5),
        ],
    )

    save_experiment_artifacts(
        artifact_dir=str(artifact_dir),
        model={"backend": "numpy_fallback", "weights": [0.2, 0.4], "bias": 0.1},
        scaler=StandardScalerState(mean_=[0.0, 0.0], scale_=[1.0, 1.0], feature_columns=["hist_low", "hist_close"]),
        feature_columns=["hist_low", "hist_close"],
        train_config={"resolved_backend": "numpy_fallback"},
        metrics={"overall": {"rmse": 0.0}},
        predictions_df=pd.DataFrame({"ticker": ["SPY"], "date": ["2024-03-05"], "pred_strength_pct": [0.5]}),
    )
    promote_buy_model(
        artifact_dir=str(artifact_dir),
        model_version="buy/v001",
        model_root=str(model_root),
        registry_path=str(model_root / "registry.json"),
    )

    monkeypatch.setattr("app.ml.buy_sub_ml.inference.update_daily_db", lambda *args, **kwargs: {"saved": 0})

    result = infer_buy_strength_signal_inputs(
        ticker="SPY",
        config_path=str(config_path),
        trade_date="2024-03-05",
        model_root=str(model_root),
    )

    assert result["ticker"] == "SPY"
    assert result["trade_date"] == "2024-03-05"
    assert result["buy_dev_pct"] == 1.0
    assert result["hist_low"] == 100.0
    assert result["model_version"] == "buy/v001"
    assert result["has_actual_trade_bar"] is True
    assert 0.0 <= result["strength_pct"] <= 1.0


def test_infer_buy_strength_signal_inputs_synthesizes_today_row_when_trade_bar_missing(tmp_path, monkeypatch):
    daily_db_path = tmp_path / "daily.db"
    config_path = _write_runtime_config(tmp_path, daily_db_path=daily_db_path)
    artifact_dir = tmp_path / "artifacts"
    model_root = tmp_path / "models" / "buy"
    _seed_daily_bars(
        daily_db_path,
        ticker="SPY",
        rows=[
            ("2024-03-01", 100.0, 101.0, 99.0, 100.5),
            ("2024-03-04", 101.0, 102.0, 100.0, 101.5),
        ],
    )

    save_experiment_artifacts(
        artifact_dir=str(artifact_dir),
        model={"backend": "numpy_fallback", "weights": [0.2, 0.4], "bias": 0.1},
        scaler=StandardScalerState(mean_=[0.0, 0.0], scale_=[1.0, 1.0], feature_columns=["hist_low", "hist_close"]),
        feature_columns=["hist_low", "hist_close"],
        train_config={"resolved_backend": "numpy_fallback"},
        metrics={"overall": {"rmse": 0.0}},
        predictions_df=pd.DataFrame({"ticker": ["SPY"], "date": ["2024-03-05"], "pred_strength_pct": [0.5]}),
    )
    promote_buy_model(
        artifact_dir=str(artifact_dir),
        model_version="buy/v001",
        model_root=str(model_root),
        registry_path=str(model_root / "registry.json"),
    )

    monkeypatch.setattr("app.ml.buy_sub_ml.inference.update_daily_db", lambda *args, **kwargs: {"saved": 0})

    result = infer_buy_strength_signal_inputs(
        ticker="SPY",
        model_version="buy/v001",
        config_path=str(config_path),
        trade_date="2024-03-05",
        model_root=str(model_root),
    )

    assert result["ticker"] == "SPY"
    assert result["trade_date"] == "2024-03-05"
    assert result["buy_dev_pct"] == 1.0
    assert result["hist_low"] == 100.0
    assert result["model_version"] == "buy/v001"
    assert result["has_actual_trade_bar"] is False
    assert 0.0 <= result["strength_pct"] <= 1.0

from __future__ import annotations

import pandas as pd

from app.ml.buy_sub_ml.trainer import fit_strength_model, predict_strength_pct, train_buy_sub_ml_model


def _build_train_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hist_z": [0.2, 0.4, 0.6, 0.8, 1.0, 1.2],
            "hist_a": [1.0, 0.9, 0.8, 0.7, 0.6, 0.5],
            "strength_pct": [0.15, 0.25, 0.45, 0.65, 0.8, 0.9],
        }
    )


def test_fit_strength_model_returns_fullfit_model_params_and_logs():
    model_params, train_logs = fit_strength_model(_build_train_frame(), backend="numpy_fallback")

    assert model_params["feature_columns"] == ["hist_a", "hist_z"]
    assert model_params["feature_order_locked"] is True
    assert model_params["target_column"] == "strength_pct"
    assert "fit_metrics" in model_params
    assert train_logs["sample_count"] == 6
    assert train_logs["feature_count"] == 2
    assert train_logs["best_epoch"] >= 1
    assert train_logs["train_losses"]


def test_predict_strength_pct_uses_saved_feature_order_and_bounded_output():
    train_df = _build_train_frame()
    model_params, _ = fit_strength_model(train_df, backend="numpy_fallback")

    hist_df = pd.DataFrame(
        {
            "hist_z": [0.3, 0.7],
            "hist_a": [0.95, 0.75],
        }
    )
    predictions = predict_strength_pct(hist_df, model_params)

    assert len(predictions) == 2
    assert all(0.0 <= value <= 1.0 for value in predictions)


def test_train_buy_sub_ml_model_returns_prediction_frame_with_strength_columns():
    dataset_df = _build_train_frame()
    dataset_df.insert(0, "ticker", ["SPY"] * len(dataset_df))
    dataset_df.insert(1, "date", pd.date_range("2024-01-01", periods=len(dataset_df), freq="D").strftime("%Y-%m-%d"))
    dataset_df.insert(2, "strength", [0.11, 0.22, 0.33, 0.44, 0.55, 0.66])

    result = train_buy_sub_ml_model(dataset_df, config={"backend": "numpy_fallback"})

    assert result["split_counts"] == {"train_rows": 6, "valid_rows": 0, "test_rows": 0}
    assert "pred_strength_pct" in result["predictions"].columns
    assert "strength" in result["predictions"].columns

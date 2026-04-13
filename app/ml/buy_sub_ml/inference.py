from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import pandas as pd

from app.ml.buy_strength_label.strength_pct import get_strength_pct_frame
from app.ml.buy_sub_ml.trainer import (
    StandardScalerState,
    load_model_payload,
    predict_strength_pct,
)
from app.ml.common.paths import (
    DEFAULT_BUY_MODEL_ROOT,
    DEFAULT_BUY_STRENGTH_DB_PATH,
    DEFAULT_BUY_TMP_OUTPUT_DIR,
    DEFAULT_FEATURE_DB_PATH,
)
from app.ml.common.utils import (
    coerce_date_str,
    ensure_directory,
    format_model_version_for_filename,
    normalize_buy_model_version,
    normalize_tickers,
    subtract_months,
)
from app.trend.features import load_feature_rows, update_feature_db


def _load_scaler(path: Path) -> StandardScalerState:
    with open(path, "rb") as file_handle:
        payload = pickle.load(file_handle)
    if isinstance(payload, StandardScalerState):
        return payload
    if isinstance(payload, dict):
        return StandardScalerState(
            mean_=list(payload["mean_"]),
            scale_=list(payload["scale_"]),
            feature_columns=list(payload["feature_columns"]),
        )
    raise ValueError("Invalid scaler payload.")


def _coerce_model_params(
    model_payload: dict[str, Any],
    *,
    scaler: StandardScalerState,
    feature_columns: list[str],
) -> dict[str, Any]:
    model_params = dict(model_payload)
    model_params.setdefault("model_type", "mlp_regressor")
    model_params.setdefault("output_activation", "sigmoid")
    model_params.setdefault("target_column", "strength_pct")
    model_params["feature_columns"] = list(feature_columns)
    model_params["feature_count"] = len(feature_columns)
    model_params["feature_order_locked"] = True
    model_params["scaler_type"] = "StandardScaler"
    model_params["scaler_mean"] = list(scaler.mean_)
    model_params["scaler_scale"] = list(scaler.scale_)
    return model_params


def infer_buy_strength_pct(
    tickers,
    start_date: str | None = None,
    end_date: str | None = None,
    strength_pct_length_month: int = 24,
    model_version: str = "",
    feature_db_path: str = str(DEFAULT_FEATURE_DB_PATH),
    strength_db_path: str = str(DEFAULT_BUY_STRENGTH_DB_PATH),
    model_root: str = str(DEFAULT_BUY_MODEL_ROOT),
    output_dir: str = str(DEFAULT_BUY_TMP_OUTPUT_DIR),
) -> str:
    normalized_tickers = normalize_tickers(tickers)
    resolved_end_date = coerce_date_str(end_date, default_today=True)
    resolved_start_date = (
        coerce_date_str(start_date, default_today=False)
        if start_date is not None
        else subtract_months(resolved_end_date, strength_pct_length_month)
    )
    if pd.Timestamp(resolved_start_date) > pd.Timestamp(resolved_end_date):
        raise ValueError("start_date must be less than or equal to end_date.")
    registry_value, version_name = normalize_buy_model_version(model_version)

    model_dir = Path(model_root).resolve() / version_name
    if not model_dir.exists():
        raise FileNotFoundError(f"Model version directory not found: {model_dir}")

    model_payload = load_model_payload(str(model_dir / "model.pt"))
    scaler = _load_scaler(model_dir / "scaler.pkl")
    feature_columns = json.loads((model_dir / "feature_columns.json").read_text(encoding="utf-8"))
    model_params = _coerce_model_params(
        model_payload,
        scaler=scaler,
        feature_columns=list(feature_columns),
    )

    feature_frames: list[pd.DataFrame] = []
    for ticker in normalized_tickers:
        update_feature_db(
            ticker=ticker,
            start_date=resolved_start_date,
            end_date=resolved_end_date,
            feature_db_path=feature_db_path,
        )
        ticker_features = load_feature_rows(
            ticker=ticker,
            start_date=resolved_start_date,
            end_date=resolved_end_date,
            feature_db_path=feature_db_path,
        )
        if ticker_features.empty:
            continue
        feature_frames.append(
            ticker_features.rename(columns={"datetime": "date"}).loc[:, ["ticker", "date", *feature_columns]].copy()
        )

    if not feature_frames:
        raise RuntimeError("No feature rows were available for inference.")

    feature_df = pd.concat(feature_frames, ignore_index=True)
    missing_feature_columns = [column for column in feature_columns if column not in feature_df.columns]
    if missing_feature_columns:
        raise ValueError(f"Feature rows are missing required columns: {missing_feature_columns}")

    inference_df = feature_df.dropna(subset=feature_columns).reset_index(drop=True)
    if inference_df.empty:
        raise RuntimeError("No inference rows remained after dropping incomplete feature values.")

    predictions = predict_strength_pct(inference_df.loc[:, feature_columns], model_params)

    result_df = inference_df.loc[:, ["ticker", "date", *feature_columns]].copy()
    label_df = get_strength_pct_frame(
        tickers=normalized_tickers,
        end_date=resolved_end_date,
        strength_pct_length_month=max(
            int(strength_pct_length_month),
            ((pd.Timestamp(resolved_end_date).year - pd.Timestamp(resolved_start_date).year) * 12)
            + (pd.Timestamp(resolved_end_date).month - pd.Timestamp(resolved_start_date).month)
            + 1,
        ),
        feature_db_path=feature_db_path,
        strength_db_path=strength_db_path,
    )
    if label_df.empty:
        result_df["strength"] = pd.NA
        result_df["strength_pct"] = pd.NA
    else:
        label_df = label_df.loc[
            (label_df["date"] >= resolved_start_date) & (label_df["date"] <= resolved_end_date)
        ].reset_index(drop=True)
        result_df = result_df.merge(
            label_df.loc[:, ["ticker", "date", "strength", "strength_pct"]],
            on=["ticker", "date"],
            how="left",
        )

    result_df["pred_strength_pct"] = predictions
    result_df["model_version"] = registry_value

    output_path = ensure_directory(output_dir) / (
        f"{'_'.join(normalized_tickers)}_{resolved_end_date}_{format_model_version_for_filename(model_version)}"
        "_strength_pct_pred.csv"
    )
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return str(output_path)


__all__ = ["infer_buy_strength_pct"]

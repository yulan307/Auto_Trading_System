from __future__ import annotations

import json
import pickle
from pathlib import Path

import pandas as pd

from app.ml.buy_strength_label.strength_pct import get_strength_pct_frame
from app.ml.buy_sub_ml.trainer import StandardScalerState, load_model_payload, predict_from_model_payload
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


def infer_buy_strength_pct(
    tickers,
    end_date: str | None,
    strength_pct_length_month: int,
    model_version: str,
    feature_db_path: str = str(DEFAULT_FEATURE_DB_PATH),
    strength_db_path: str = str(DEFAULT_BUY_STRENGTH_DB_PATH),
    model_root: str = str(DEFAULT_BUY_MODEL_ROOT),
    output_dir: str = str(DEFAULT_BUY_TMP_OUTPUT_DIR),
) -> str:
    normalized_tickers = normalize_tickers(tickers)
    resolved_end_date = coerce_date_str(end_date, default_today=True)
    start_date = subtract_months(resolved_end_date, strength_pct_length_month)
    registry_value, version_name = normalize_buy_model_version(model_version)

    model_dir = Path(model_root).resolve() / version_name
    if not model_dir.exists():
        raise FileNotFoundError(f"Model version directory not found: {model_dir}")

    model_payload = load_model_payload(str(model_dir / "model.pt"))
    scaler = _load_scaler(model_dir / "scaler.pkl")
    feature_columns = json.loads((model_dir / "feature_columns.json").read_text(encoding="utf-8"))

    feature_frames: list[pd.DataFrame] = []
    for ticker in normalized_tickers:
        update_feature_db(
            ticker=ticker,
            start_date=start_date,
            end_date=resolved_end_date,
            feature_db_path=feature_db_path,
        )
        ticker_features = load_feature_rows(
            ticker=ticker,
            start_date=start_date,
            end_date=resolved_end_date,
            feature_db_path=feature_db_path,
        )
        if ticker_features.empty:
            continue
        feature_frames.append(ticker_features.rename(columns={"datetime": "date"}))

    if not feature_frames:
        raise RuntimeError("No feature rows were available for inference.")

    feature_df = pd.concat(feature_frames, ignore_index=True)
    for column in feature_columns:
        if column not in feature_df.columns:
            feature_df[column] = pd.NA
    feature_df = feature_df.dropna(subset=feature_columns).reset_index(drop=True)
    values = feature_df.loc[:, feature_columns].to_numpy(dtype=float)
    scaled_values = scaler.transform(values)
    predictions = predict_from_model_payload(model_payload, scaled_values)

    result_df = feature_df.loc[:, ["ticker", "date"]].copy()
    result_df["pred_strength_pct"] = predictions
    result_df["model_version"] = registry_value

    true_df = get_strength_pct_frame(
        tickers=normalized_tickers,
        end_date=resolved_end_date,
        strength_pct_length_month=strength_pct_length_month,
        feature_db_path=feature_db_path,
        strength_db_path=strength_db_path,
    )
    if not true_df.empty:
        true_df = true_df.rename(columns={"strength_pct": "true_strength_pct"})
        result_df = result_df.merge(
            true_df.loc[:, ["ticker", "date", "true_strength_pct"]],
            on=["ticker", "date"],
            how="left",
        )

    output_path = ensure_directory(output_dir) / (
        f"{'_'.join(normalized_tickers)}_{resolved_end_date}_{format_model_version_for_filename(model_version)}"
        "_strength_pct_pred.csv"
    )
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return str(output_path)

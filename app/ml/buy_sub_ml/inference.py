from __future__ import annotations

import json
import pickle
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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
from app.data.repository import load_bars
from app.data.updater import update_daily_db
from app.runtime.config_loader import load_config
from app.trend.features import (
    build_trend_feature_frame,
    compute_fetch_start_date,
    load_feature_rows,
    update_feature_db,
)


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


def _load_inference_bundle(
    *,
    model_version: str,
    model_root: str,
) -> tuple[str, list[str], dict[str, Any]]:
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
    return registry_value, list(feature_columns), model_params


def _resolve_runtime_trade_date(
    *,
    config: dict[str, Any],
    trade_date: str | date | datetime | None = None,
) -> str:
    if trade_date is not None:
        return coerce_date_str(trade_date, default_today=False)

    timezone_name = str(config.get("timezone") or "UTC")
    return datetime.now(ZoneInfo(timezone_name)).date().isoformat()


def _prepare_runtime_daily_frame(
    *,
    daily_rows: list[dict[str, Any]],
    trade_date: str,
) -> tuple[pd.DataFrame, bool]:
    if not daily_rows:
        raise RuntimeError("No daily bars were available to build runtime features.")

    frame = pd.DataFrame(daily_rows)
    required_columns = [
        "datetime",
        "interval",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source",
        "update_time",
    ]
    missing_columns = [column for column in required_columns if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Daily bars are missing required columns: {missing_columns}")

    result = frame.loc[:, required_columns].copy()
    result["datetime"] = pd.to_datetime(result["datetime"], errors="coerce").dt.strftime("%Y-%m-%d")
    if result["datetime"].isna().any():
        raise ValueError("Found invalid datetime values while preparing runtime features.")

    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce")

    result["interval"] = result["interval"].fillna("1d").astype(str)
    result["source"] = result["source"].fillna("unknown").astype(str)
    result["update_time"] = result["update_time"].fillna("").astype(str)
    result = result.sort_values("datetime").drop_duplicates(subset=["datetime"], keep="last").reset_index(drop=True)

    has_actual_trade_bar = trade_date in set(result["datetime"].tolist())
    if not has_actual_trade_bar:
        placeholder_row = {
            "datetime": trade_date,
            "interval": "1d",
            "open": float("nan"),
            "high": float("nan"),
            "low": float("nan"),
            "close": float("nan"),
            "volume": float("nan"),
            "source": "runtime_placeholder",
            "update_time": datetime.now(timezone.utc).isoformat(),
        }
        result = pd.concat([result, pd.DataFrame([placeholder_row])], ignore_index=True)
        result = result.sort_values("datetime").drop_duplicates(subset=["datetime"], keep="last").reset_index(drop=True)

    return result, has_actual_trade_bar


def _load_runtime_feature_row(
    *,
    ticker: str,
    trade_date: str,
    daily_db_path: str,
) -> tuple[pd.Series, bool]:
    fetch_start_date = compute_fetch_start_date(trade_date)
    update_daily_db(
        ticker=ticker,
        start_date=fetch_start_date,
        end_date=trade_date,
        db_path=daily_db_path,
    )
    daily_rows = load_bars(
        db_path=daily_db_path,
        table_name="daily_bars",
        ticker=ticker,
        interval="1d",
        start_date=fetch_start_date,
        end_date=trade_date,
    )
    prepared_daily_df, has_actual_trade_bar = _prepare_runtime_daily_frame(
        daily_rows=daily_rows,
        trade_date=trade_date,
    )
    feature_df = build_trend_feature_frame(prepared_daily_df)
    trade_rows = feature_df.loc[feature_df["datetime"] == trade_date].reset_index(drop=True)
    if trade_rows.empty:
        raise RuntimeError(f"Runtime feature row was not produced for ticker={ticker} trade_date={trade_date}.")
    return trade_rows.iloc[0], has_actual_trade_bar


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
    registry_value, feature_columns, model_params = _load_inference_bundle(
        model_version=model_version,
        model_root=model_root,
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


def infer_buy_strength_signal_inputs(
    *,
    ticker: str,
    model_version: str | None = None,
    config_path: str = "config/backtest.yaml",
    trade_date: str | date | datetime | None = None,
    model_root: str = str(DEFAULT_BUY_MODEL_ROOT),
) -> dict[str, Any]:
    config = load_config(config_path)
    resolved_trade_date = _resolve_runtime_trade_date(config=config, trade_date=trade_date)
    resolved_model_version = str(model_version or config.get("ml", {}).get("buy_model_version") or "").strip()
    if not resolved_model_version:
        raise ValueError("model_version must be provided directly or configured under ml.buy_model_version.")

    registry_value, feature_columns, model_params = _load_inference_bundle(
        model_version=resolved_model_version,
        model_root=model_root,
    )
    feature_row, has_actual_trade_bar = _load_runtime_feature_row(
        ticker=str(ticker).strip().upper(),
        trade_date=resolved_trade_date,
        daily_db_path=str(config["data"]["daily_db_path"]),
    )

    missing_feature_columns = [column for column in feature_columns if column not in feature_row.index]
    if missing_feature_columns:
        raise ValueError(f"Runtime feature row is missing required columns: {missing_feature_columns}")

    inference_df = pd.DataFrame([{column: feature_row[column] for column in feature_columns}])
    inference_df = inference_df.apply(pd.to_numeric, errors="coerce")
    if inference_df.isna().any().any():
        missing_runtime_columns = [column for column in feature_columns if pd.isna(inference_df.iloc[0][column])]
        raise RuntimeError(
            "Runtime feature row contains incomplete model inputs: "
            f"{missing_runtime_columns}. Check whether the warmup window is sufficient."
        )

    strength_pct = float(predict_strength_pct(inference_df, model_params)[0])
    hist_low_value = feature_row.get("hist_low", pd.NA)
    return {
        "ticker": str(ticker).strip().upper(),
        "trade_date": resolved_trade_date,
        "strength_pct": strength_pct,
        "buy_dev_pct": 1.0,
        "hist_low": None if pd.isna(hist_low_value) else float(hist_low_value),
        "model_version": registry_value,
        "has_actual_trade_bar": has_actual_trade_bar,
    }


__all__ = ["infer_buy_strength_pct", "infer_buy_strength_signal_inputs"]

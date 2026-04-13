from __future__ import annotations

from datetime import datetime, timezone

from app.ml.buy_sub_ml.artifact import save_experiment_artifacts
from app.ml.buy_sub_ml.dataset import build_buy_sub_ml_dataset
from app.ml.buy_sub_ml.trainer import train_buy_sub_ml_model
from app.ml.common.paths import DEFAULT_BUY_STRENGTH_DB_PATH, DEFAULT_BUY_TMP_OUTPUT_DIR, DEFAULT_FEATURE_DB_PATH
from app.ml.common.utils import coerce_date_str, ensure_directory, format_model_version_for_filename, normalize_tickers


def run_buy_sub_ml_experiment(
    tickers,
    end_date: str | None,
    strength_pct_length_month: int,
    model_version: str | None = None,
    feature_db_path: str = str(DEFAULT_FEATURE_DB_PATH),
    strength_db_path: str = str(DEFAULT_BUY_STRENGTH_DB_PATH),
    output_dir: str = str(DEFAULT_BUY_TMP_OUTPUT_DIR),
    config: dict | None = None,
) -> dict:
    normalized_tickers = normalize_tickers(tickers)
    resolved_end_date = coerce_date_str(end_date, default_today=True)
    dataset_df = build_buy_sub_ml_dataset(
        tickers=normalized_tickers,
        end_date=resolved_end_date,
        strength_pct_length_month=strength_pct_length_month,
        feature_db_path=feature_db_path,
        strength_db_path=strength_db_path,
    )
    train_result = train_buy_sub_ml_model(dataset_df, config=config)
    feature_columns = list(train_result["model_params"]["feature_columns"])

    token = format_model_version_for_filename(model_version or "experiment")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = ensure_directory(output_dir) / f"{run_id}_{token}"
    save_experiment_artifacts(
        artifact_dir=str(artifact_dir),
        model=train_result["model"],
        scaler=train_result["scaler"],
        feature_columns=feature_columns,
        train_config=train_result["train_config"],
        metrics=train_result["metrics"],
        predictions_df=train_result["predictions"],
    )

    split_counts = train_result["split_counts"]
    train_logs = train_result["train_logs"]
    fit_metrics = train_logs["fullfit_metrics"]
    return {
        "tickers": normalized_tickers,
        "sample_count": train_logs["sample_count"],
        "train_rows": split_counts["train_rows"],
        "valid_rows": split_counts["valid_rows"],
        "test_rows": split_counts["test_rows"],
        "feature_count": len(feature_columns),
        "best_epoch": train_logs["best_epoch"],
        "best_train_loss": train_logs["best_train_loss"],
        "fit_metrics": fit_metrics,
        "artifact_dir": str(artifact_dir),
        "status": "ok",
    }

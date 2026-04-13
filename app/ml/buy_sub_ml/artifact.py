from __future__ import annotations

import json
import pickle
from datetime import datetime, timezone
from pathlib import Path

from app.ml.buy_sub_ml.trainer import StandardScalerState, save_model_payload
from app.ml.common.utils import ensure_directory


def save_experiment_artifacts(
    artifact_dir: str,
    model,
    scaler,
    feature_columns: list[str],
    train_config: dict,
    metrics: dict,
    predictions_df,
) -> None:
    target_dir = ensure_directory(artifact_dir)
    model_path = target_dir / "model.pt"
    save_model_payload(str(model_path), model)

    scaler_path = target_dir / "scaler.pkl"
    if isinstance(scaler, StandardScalerState):
        payload = scaler.to_dict()
    else:
        payload = scaler
    with open(scaler_path, "wb") as file_handle:
        pickle.dump(payload, file_handle)

    (target_dir / "feature_columns.json").write_text(
        json.dumps(feature_columns, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (target_dir / "train_config.json").write_text(
        json.dumps(train_config, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (target_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    predictions_df.to_csv(target_dir / "predictions.csv", index=False, encoding="utf-8-sig")
    overall_metrics = metrics.get("overall", {})
    (target_dir / "notes.md").write_text(
        "\n".join(
            [
                "# Buy Sub ML Experiment",
                "",
                f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
                f"- feature_count: {len(feature_columns)}",
                f"- prediction_rows: {len(predictions_df)}",
                f"- rmse: {overall_metrics.get('rmse')}",
                f"- r2: {overall_metrics.get('r2')}",
            ]
        ),
        encoding="utf-8",
    )

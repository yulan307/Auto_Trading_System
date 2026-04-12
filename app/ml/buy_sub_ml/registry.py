from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.ml.common.paths import DEFAULT_BUY_MODEL_ROOT, DEFAULT_BUY_REGISTRY_PATH
from app.ml.common.schemas import BUY_MODEL_REGISTRY_TEMPLATE
from app.ml.common.utils import ensure_directory, normalize_buy_model_version


REQUIRED_MODEL_FILES = [
    "model.pt",
    "scaler.pkl",
    "feature_columns.json",
    "train_config.json",
    "metrics.json",
    "notes.md",
]


def _ensure_registry_file(registry_path: str) -> Path:
    target = Path(registry_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(json.dumps(BUY_MODEL_REGISTRY_TEMPLATE, indent=2), encoding="utf-8")
    return target


def promote_buy_model(
    artifact_dir: str,
    model_version: str,
    model_root: str = str(DEFAULT_BUY_MODEL_ROOT),
    registry_path: str = str(DEFAULT_BUY_REGISTRY_PATH),
) -> dict:
    artifact_path = Path(artifact_dir).resolve()
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact directory not found: {artifact_path}")

    registry_value, version_name = normalize_buy_model_version(model_version)
    model_root_path = ensure_directory(model_root)
    target_dir = model_root_path / version_name
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename in REQUIRED_MODEL_FILES:
        source = artifact_path / filename
        if not source.exists():
            raise FileNotFoundError(f"Required artifact file is missing: {source}")
        shutil.copy2(source, target_dir / filename)

    registry_file = _ensure_registry_file(registry_path)
    registry_data = json.loads(registry_file.read_text(encoding="utf-8"))
    versions = registry_data.setdefault("versions", {})
    versions[registry_value] = {
        "path": str(target_dir),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
    }
    registry_data["active_version"] = registry_value
    registry_file.write_text(json.dumps(registry_data, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "active_version": registry_value,
        "model_dir": str(target_dir),
        "registry_path": str(registry_file),
        "status": "ok",
    }

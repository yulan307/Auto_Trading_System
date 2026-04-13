from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def load_buy_model_registry(registry_path: str = str(DEFAULT_BUY_REGISTRY_PATH)) -> dict[str, Any]:
    registry_file = _ensure_registry_file(registry_path)
    payload = json.loads(registry_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Buy model registry payload must be a JSON object.")
    payload.setdefault("active_version", None)
    payload.setdefault("versions", {})
    return payload


def list_buy_model_versions(
    model_root: str = str(DEFAULT_BUY_MODEL_ROOT),
    registry_path: str = str(DEFAULT_BUY_REGISTRY_PATH),
) -> list[dict[str, Any]]:
    registry_data = load_buy_model_registry(registry_path)
    active_version = registry_data.get("active_version")
    versions = registry_data.get("versions", {})

    model_root_path = ensure_directory(model_root)
    discovered_dirs = {
        child.name: child
        for child in model_root_path.iterdir()
        if child.is_dir()
    }

    entries: dict[str, dict[str, Any]] = {}
    for registry_value, payload in versions.items():
        _, version_name = normalize_buy_model_version(str(registry_value))
        entry_path = Path(str(payload.get("path") or (model_root_path / version_name))).resolve()
        entries[version_name] = {
            "registry_value": str(registry_value),
            "version_name": version_name,
            "path": str(entry_path),
            "exists": entry_path.exists(),
            "is_active": str(registry_value) == str(active_version),
            "promoted_at": payload.get("promoted_at"),
        }

    for version_name, path in discovered_dirs.items():
        entries.setdefault(
            version_name,
            {
                "registry_value": f"buy/{version_name}",
                "version_name": version_name,
                "path": str(path.resolve()),
                "exists": True,
                "is_active": f"buy/{version_name}" == str(active_version),
                "promoted_at": None,
            },
        )

    return sorted(
        entries.values(),
        key=lambda item: (
            0 if item["is_active"] else 1,
            str(item["version_name"]).lower(),
        ),
    )


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


__all__ = [
    "list_buy_model_versions",
    "load_buy_model_registry",
    "promote_buy_model",
]

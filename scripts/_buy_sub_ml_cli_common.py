from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ml.common.paths import DEFAULT_BUY_MODEL_ROOT, DEFAULT_BUY_REGISTRY_PATH
from app.ml.common.utils import normalize_buy_model_version


def load_model_registry(
    model_root: str = str(DEFAULT_BUY_MODEL_ROOT),
    registry_path: str = str(DEFAULT_BUY_REGISTRY_PATH),
) -> tuple[dict[str, Any], Path]:
    registry_file = Path(registry_path).resolve()
    if registry_file.exists():
        return json.loads(registry_file.read_text(encoding="utf-8")), registry_file
    return {"active_version": None, "versions": {}}, registry_file


def list_available_models(
    model_root: str = str(DEFAULT_BUY_MODEL_ROOT),
    registry_path: str = str(DEFAULT_BUY_REGISTRY_PATH),
) -> list[dict[str, str | bool]]:
    registry_data, _ = load_model_registry(model_root=model_root, registry_path=registry_path)
    active_version = registry_data.get("active_version")
    version_entries = registry_data.get("versions", {})
    models: list[dict[str, str | bool]] = []

    for registry_value, payload in sorted(version_entries.items()):
        version_name = normalize_buy_model_version(str(registry_value))[1]
        model_dir = Path(str(payload.get("path", Path(model_root).resolve() / version_name))).resolve()
        if not model_dir.exists():
            continue
        models.append(
            {
                "registry_value": str(registry_value),
                "version_name": version_name,
                "model_dir": str(model_dir),
                "is_active": str(registry_value) == str(active_version),
            }
        )

    root_dir = Path(model_root).resolve()
    if root_dir.exists():
        known_versions = {str(item["registry_value"]) for item in models}
        for child in sorted(root_dir.iterdir()):
            if not child.is_dir():
                continue
            registry_value = f"buy/{child.name}"
            if registry_value in known_versions:
                continue
            models.append(
                {
                    "registry_value": registry_value,
                    "version_name": child.name,
                    "model_dir": str(child.resolve()),
                    "is_active": registry_value == str(active_version),
                }
            )

    return models


def prompt_menu_choice(options: list[str], title: str) -> int:
    if not options:
        raise ValueError("options must not be empty.")
    print(title)
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option}")

    while True:
        raw_value = input("请输入序号: ").strip()
        if raw_value.isdigit():
            numeric = int(raw_value)
            if 1 <= numeric <= len(options):
                return numeric - 1
        print("输入无效，请重新输入有效序号。")


def prompt_model_selection(
    model_root: str = str(DEFAULT_BUY_MODEL_ROOT),
    registry_path: str = str(DEFAULT_BUY_REGISTRY_PATH),
    title: str = "请选择模型：",
) -> dict[str, str | bool]:
    models = list_available_models(model_root=model_root, registry_path=registry_path)
    if not models:
        raise RuntimeError("当前没有可选模型，请先训练并发布模型。")

    options = []
    for item in models:
        active_tag = " [active]" if bool(item["is_active"]) else ""
        options.append(f"{item['registry_value']} -> {item['model_dir']}{active_tag}")
    selected_index = prompt_menu_choice(options, title)
    return models[selected_index]


def load_train_config_from_model_dir(model_dir: str) -> dict[str, Any]:
    config_path = Path(model_dir).resolve() / "train_config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))

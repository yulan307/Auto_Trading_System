from __future__ import annotations

import json

from scripts._buy_sub_ml_cli_common import list_available_models, load_train_config_from_model_dir


def test_list_available_models_reads_registry_and_model_dir(tmp_path):
    model_root = tmp_path / "models" / "buy"
    model_dir = model_root / "v001"
    model_dir.mkdir(parents=True)
    registry_path = model_root / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "active_version": "buy/v001",
                "versions": {
                    "buy/v001": {
                        "path": str(model_dir),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    models = list_available_models(model_root=str(model_root), registry_path=str(registry_path))

    assert len(models) == 1
    assert models[0]["registry_value"] == "buy/v001"
    assert models[0]["is_active"] is True


def test_load_train_config_from_model_dir_returns_json_payload(tmp_path):
    model_dir = tmp_path / "models" / "buy" / "v001"
    model_dir.mkdir(parents=True)
    (model_dir / "train_config.json").write_text(
        json.dumps({"backend": "numpy_fallback", "batch_size": 16}),
        encoding="utf-8",
    )

    payload = load_train_config_from_model_dir(str(model_dir))

    assert payload == {"backend": "numpy_fallback", "batch_size": 16}

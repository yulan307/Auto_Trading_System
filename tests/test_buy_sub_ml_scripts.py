from __future__ import annotations

from pathlib import Path

from scripts.train_buy_sub_ml import build_parser as build_train_parser
from scripts.infer_buy_sub_ml import build_parser as build_infer_parser
from scripts._buy_sub_ml_cli_common import resolve_model_reference


def test_train_script_parser_accepts_non_interactive_flags():
    parser = build_train_parser()
    args = parser.parse_args(
        [
            "--tickers",
            "SPY",
            "--end-date",
            "2026-04-14",
            "--mode",
            "new",
            "--model",
            "buy/demo_v001",
        ]
    )

    assert args.mode == "new"
    assert args.model == "buy/demo_v001"


def test_train_script_parser_accepts_output_model_for_update_mode():
    parser = build_train_parser()
    args = parser.parse_args(
        [
            "--tickers",
            "SPY",
            "--end-date",
            "2026-04-14",
            "--mode",
            "update",
            "--model",
            "buy/base_v001",
            "--output-model",
            "buy/updated_v002",
        ]
    )

    assert args.mode == "update"
    assert args.model == "buy/base_v001"
    assert args.output_model == "buy/updated_v002"


def test_infer_script_parser_accepts_non_interactive_flags():
    parser = build_infer_parser()
    args = parser.parse_args(
        [
            "--tickers",
            "SPY",
            "--start-date",
            "2026-04-01",
            "--end-date",
            "2026-04-14",
            "--mode",
            "infer",
            "--model",
            "buy/demo_v001",
        ]
    )

    assert args.mode == "infer"
    assert args.model == "buy/demo_v001"


def test_resolve_model_reference_accepts_registry_value_or_version_name(tmp_path):
    model_root = tmp_path / "models" / "buy"
    model_dir = model_root / "demo_v001"
    model_dir.mkdir(parents=True)
    registry_path = model_root / "registry.json"
    registry_path.write_text(
        '{\n  "active_version": "buy/demo_v001",\n  "versions": {\n    "buy/demo_v001": {\n      "path": "'
        + str(model_dir).replace("\\", "\\\\")
        + '"\n    }\n  }\n}',
        encoding="utf-8",
    )

    by_registry = resolve_model_reference("buy/demo_v001", model_root=str(model_root), registry_path=str(registry_path))
    by_name = resolve_model_reference("demo_v001", model_root=str(model_root), registry_path=str(registry_path))

    assert by_registry["model_dir"] == str(Path(model_dir).resolve())
    assert by_name["registry_value"] == "buy/demo_v001"

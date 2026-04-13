from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ml.buy_sub_ml.experiment import run_buy_sub_ml_experiment
from app.ml.buy_sub_ml.registry import promote_buy_model
from app.ml.common.paths import (
    DEFAULT_BUY_MODEL_ROOT,
    DEFAULT_BUY_REGISTRY_PATH,
    DEFAULT_BUY_STRENGTH_DB_PATH,
    DEFAULT_BUY_TMP_OUTPUT_DIR,
    DEFAULT_FEATURE_DB_PATH,
)
from app.ml.common.utils import normalize_buy_model_version, normalize_tickers
from scripts._buy_sub_ml_cli_common import (
    load_train_config_from_model_dir,
    prompt_menu_choice,
    prompt_model_selection,
    resolve_model_reference,
)


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train and publish a buy_sub_ml model.")
    parser.add_argument("--tickers", nargs="+", required=True, help="One or more ticker symbols.")
    parser.add_argument("--end-date", required=True, help="Training end date in YYYY-MM-DD.")
    parser.add_argument("--strength-pct-length-month", type=int, default=24, help="Label window length in months.")
    parser.add_argument("--feature-db-path", default=str(DEFAULT_FEATURE_DB_PATH))
    parser.add_argument("--strength-db-path", default=str(DEFAULT_BUY_STRENGTH_DB_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_BUY_TMP_OUTPUT_DIR))
    parser.add_argument("--model-root", default=str(DEFAULT_BUY_MODEL_ROOT))
    parser.add_argument("--registry-path", default=str(DEFAULT_BUY_REGISTRY_PATH))
    parser.add_argument("--mode", choices=["new", "update"], help="Non-interactive mode. Use with --model.")
    parser.add_argument(
        "--model",
        help=(
            "Non-interactive model argument. "
            "For --mode new, this is the new model version name. "
            "For --mode update, this is the existing model to update from."
        ),
    )
    parser.add_argument(
        "--output-model",
        help=(
            "Optional target version name for non-interactive update mode. "
            "If omitted, the script auto-generates a timestamped version name."
        ),
    )
    return parser


def _build_auto_version_name(prefix: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{timestamp}"


def _normalize_target_version_name(model_reference: str) -> str:
    _, version_name = normalize_buy_model_version(model_reference)
    if not version_name:
        raise RuntimeError("Target model version name must not be empty.")
    return version_name


def _select_run_mode_interactive() -> tuple[str, str, dict]:
    choice = prompt_menu_choice(
        [
            "学习新模型",
            "更新已有模型",
        ],
        "请选择运行模式：",
    )
    if choice == 0:
        return "new", _build_auto_version_name("buy_sub_ml"), {}

    selected_model = prompt_model_selection(title="请选择要更新的已有模型：")
    base_registry_value = str(selected_model["registry_value"])
    base_version_name = str(selected_model["version_name"])
    config = load_train_config_from_model_dir(str(selected_model["model_dir"]))
    config.pop("resolved_backend", None)
    return base_registry_value, _build_auto_version_name(f"{base_version_name}_update"), config


def _select_run_mode_non_interactive(args: argparse.Namespace) -> tuple[str, str, dict]:
    if not args.mode or not args.model:
        raise RuntimeError("Non-interactive mode requires both --mode and --model.")

    if args.mode == "new":
        if args.output_model:
            raise RuntimeError("--output-model is only supported together with --mode update.")
        return "new", _normalize_target_version_name(args.model), {}

    selected_model = resolve_model_reference(
        args.model,
        model_root=args.model_root,
        registry_path=args.registry_path,
    )
    base_registry_value = str(selected_model["registry_value"])
    base_version_name = str(selected_model["version_name"])
    config = load_train_config_from_model_dir(str(selected_model["model_dir"]))
    config.pop("resolved_backend", None)
    target_version_name = (
        _normalize_target_version_name(args.output_model)
        if args.output_model
        else _build_auto_version_name(f"{base_version_name}_update")
    )
    return base_registry_value, target_version_name, config


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    normalized_tickers = normalize_tickers(args.tickers)
    if bool(args.mode) != bool(args.model):
        raise RuntimeError("--mode and --model must be provided together, or both omitted for interactive mode.")
    if args.output_model and not (args.mode == "update" and args.model):
        raise RuntimeError("--output-model can only be used with non-interactive --mode update.")

    if args.mode and args.model:
        mode_value, new_version_name, train_config = _select_run_mode_non_interactive(args)
    else:
        mode_value, new_version_name, train_config = _select_run_mode_interactive()

    result = run_buy_sub_ml_experiment(
        tickers=normalized_tickers,
        end_date=args.end_date,
        strength_pct_length_month=int(args.strength_pct_length_month),
        model_version=new_version_name,
        feature_db_path=args.feature_db_path,
        strength_db_path=args.strength_db_path,
        output_dir=args.output_dir,
        config=train_config or None,
    )
    promoted = promote_buy_model(
        artifact_dir=result["artifact_dir"],
        model_version=f"buy/{new_version_name}",
        model_root=args.model_root,
        registry_path=args.registry_path,
    )

    output = {
        "status": "ok",
        "mode": "new" if mode_value == "new" else "update",
        "base_model_version": None if mode_value == "new" else mode_value,
        "output_model_version": promoted["active_version"],
        "tickers": normalized_tickers,
        "end_date": args.end_date,
        "artifact_dir": result["artifact_dir"],
        "model_dir": promoted["model_dir"],
        "active_version": promoted["active_version"],
        "sample_count": result["sample_count"],
        "feature_count": result["feature_count"],
        "best_epoch": result["best_epoch"],
        "best_train_loss": result["best_train_loss"],
        "fit_metrics": result["fit_metrics"],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    LOGGER.info("training_complete model_dir=%s", promoted["model_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

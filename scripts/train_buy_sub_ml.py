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
from app.ml.common.utils import normalize_tickers
from scripts._buy_sub_ml_cli_common import load_train_config_from_model_dir, prompt_menu_choice, prompt_model_selection


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
    return parser


def _build_auto_version_name(prefix: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{timestamp}"


def _select_run_mode() -> tuple[str, str | None, dict]:
    choice = prompt_menu_choice(
        [
            "学习新模型",
            "更新已有模型",
        ],
        "请选择运行模式：",
    )
    if choice == 0:
        version_name = _build_auto_version_name("buy_sub_ml")
        return "new", version_name, {}

    selected_model = prompt_model_selection(title="请选择要更新的已有模型：")
    base_registry_value = str(selected_model["registry_value"])
    base_version_name = str(selected_model["version_name"])
    config = load_train_config_from_model_dir(str(selected_model["model_dir"]))
    new_version_name = _build_auto_version_name(f"{base_version_name}_update")
    config.pop("resolved_backend", None)
    return base_registry_value, new_version_name, config


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    normalized_tickers = normalize_tickers(args.tickers)
    mode_value, new_version_name, train_config = _select_run_mode()
    if not new_version_name:
        raise RuntimeError("Failed to resolve target model version.")

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

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ml.buy_sub_ml.inference import infer_buy_strength_pct
from app.ml.common.paths import (
    DEFAULT_BUY_MODEL_ROOT,
    DEFAULT_BUY_REGISTRY_PATH,
    DEFAULT_BUY_STRENGTH_DB_PATH,
    DEFAULT_BUY_TMP_OUTPUT_DIR,
    DEFAULT_FEATURE_DB_PATH,
)
from app.ml.common.utils import normalize_tickers
from scripts._buy_sub_ml_cli_common import prompt_model_selection


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run buy_sub_ml inference and export per-ticker CSV files.")
    parser.add_argument("--tickers", nargs="+", required=True, help="One or more ticker symbols.")
    parser.add_argument("--start-date", required=True, help="Inference start date in YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Inference end date in YYYY-MM-DD.")
    parser.add_argument("--strength-pct-length-month", type=int, default=24, help="Fallback label window length.")
    parser.add_argument("--feature-db-path", default=str(DEFAULT_FEATURE_DB_PATH))
    parser.add_argument("--strength-db-path", default=str(DEFAULT_BUY_STRENGTH_DB_PATH))
    parser.add_argument("--model-root", default=str(DEFAULT_BUY_MODEL_ROOT))
    parser.add_argument("--registry-path", default=str(DEFAULT_BUY_REGISTRY_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_BUY_TMP_OUTPUT_DIR))
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    normalized_tickers = normalize_tickers(args.tickers)
    selected_model = prompt_model_selection(
        model_root=args.model_root,
        registry_path=args.registry_path,
        title="请选择用于推理的模型：",
    )
    selected_model_version = str(selected_model["registry_value"])

    output_paths: dict[str, str] = {}
    for ticker in normalized_tickers:
        output_paths[ticker] = infer_buy_strength_pct(
            tickers=[ticker],
            start_date=args.start_date,
            end_date=args.end_date,
            strength_pct_length_month=int(args.strength_pct_length_month),
            model_version=selected_model_version,
            feature_db_path=args.feature_db_path,
            strength_db_path=args.strength_db_path,
            model_root=args.model_root,
            output_dir=args.output_dir,
        )

    output = {
        "status": "ok",
        "model_version": selected_model_version,
        "model_dir": selected_model["model_dir"],
        "tickers": normalized_tickers,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "result_csv_by_ticker": output_paths,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    LOGGER.info("inference_complete model_version=%s tickers=%s", selected_model_version, normalized_tickers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

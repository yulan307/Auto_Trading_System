from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backtest.engine import run_backtest
from app.data.db import initialize_all_databases
from app.data.providers.yfinance_provider import YFinanceProvider
from app.data.repository import load_bars
from app.data.updater import update_symbol_data
from app.runtime.controller import init_runtime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a minimal end-to-end backtest loop.")
    parser.add_argument("--config", default="config/backtest.yaml", help="Path to YAML config file.")
    parser.add_argument("--ticker", required=True, help="Ticker symbol, e.g. SPY.")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD).")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD).")
    parser.add_argument(
        "--output",
        default="outputs/backtest_minimal_result.json",
        help="Path to save JSON backtest output.",
    )
    return parser.parse_args()


def _ensure_daily_data_ready(*, config: dict, ticker: str, start_date: str, end_date: str) -> dict:
    provider_name = str(config["data"].get("daily_provider", "local")).lower()
    daily_db_path = config["data"]["daily_db_path"]

    if provider_name == "yfinance":
        result = update_symbol_data(
            provider=YFinanceProvider(),
            db_path=daily_db_path,
            ticker=ticker,
            interval="1d",
            start_date=start_date,
            end_date=end_date,
            source="yfinance",
        )
    elif provider_name == "local":
        result = {
            "ticker": ticker,
            "interval": "1d",
            "fetched": 0,
            "saved": 0,
            "table": "daily_bars",
            "source": "local",
        }
    else:
        raise ValueError(f"Unsupported daily_provider for backtest init: {provider_name}")

    rows = load_bars(
        daily_db_path,
        "daily_bars",
        ticker=ticker,
        interval="1d",
        start_date=start_date,
        end_date=end_date,
    )
    if not rows:
        raise RuntimeError(
            "No daily bars available after initialization. "
            "Please import local data or use data.daily_provider=yfinance."
        )

    result["available_bars"] = len(rows)
    return result


def main() -> int:
    args = parse_args()
    runtime_context = init_runtime(args.config)
    initialize_all_databases(runtime_context["config"])

    data_init = _ensure_daily_data_ready(
        config=runtime_context["config"],
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    result = run_backtest(
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
        runtime_context=runtime_context,
    )
    result["data_init"] = data_init

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {"status": result["status"], "output": str(output_path.resolve()), "available_bars": data_init["available_bars"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

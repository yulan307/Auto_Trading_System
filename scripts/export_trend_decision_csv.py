from __future__ import annotations

import argparse
import csv
import logging
import sys
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.repository import init_price_db, load_bars
from app.data.updater import update_symbol_data
from app.data.providers.yfinance_provider import YFinanceProvider
from app.trend.features import compute_ma_features
from app.trend.classifier import classify_trend


LOGGER = logging.getLogger(__name__)
DEFAULT_DAILY_DB_PATH = PROJECT_ROOT / "data" / "raw" / "daily.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"


def _parse_date(raw: str) -> date:
    return datetime.fromisoformat(raw).date()


def _to_date(raw: Any) -> date:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    return datetime.fromisoformat(str(raw)).date()


def export_trend_decision_csv(
    *,
    ticker: str,
    start_date: date,
    end_date: date,
    interval: str = "1d",
    db_path: str | Path = DEFAULT_DAILY_DB_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    warmup_days: int = 180,
    provider: Any | None = None,
    source: str = "yfinance",
) -> Path:
    if interval != "1d":
        raise ValueError("export_trend_decision_csv currently only supports interval='1d'.")
    if end_date < start_date:
        raise ValueError("end_date must be greater than or equal to start_date.")

    db_path = Path(db_path)
    output_dir = Path(output_dir)
    warmup_start = start_date - timedelta(days=warmup_days)

    LOGGER.info("Initializing price DB: %s", db_path)
    init_price_db(db_path, "daily_bars")

    provider_instance = provider or YFinanceProvider()
    LOGGER.info(
        "Updating symbol data for %s interval=%s warmup_start=%s end_date=%s",
        ticker,
        interval,
        warmup_start,
        end_date,
    )
    update_result = update_symbol_data(
        provider=provider_instance,
        db_path=str(db_path),
        ticker=ticker,
        interval=interval,
        start_date=warmup_start,
        end_date=end_date,
        source=source,
    )
    LOGGER.info("Data update result: %s", update_result)

    LOGGER.info("Loading bars from DB for ticker=%s", ticker)
    bars = load_bars(
        db_path=db_path,
        table_name="daily_bars",
        ticker=ticker,
        interval=interval,
        start_date=warmup_start,
        end_date=end_date,
    )
    if not bars:
        raise RuntimeError(
            f"No bars found in daily.db after update. ticker={ticker}, interval={interval}, "
            f"range=[{warmup_start}, {end_date}]"
        )

    closes: list[float] = []
    row_buffer: list[dict[str, Any]] = []
    for bar in bars:
        closes.append(float(bar["close"]))
        trade_date = _to_date(bar["datetime"])

        try:
            features = compute_ma_features(ticker=ticker, trade_date=trade_date, closes=closes)
        except ValueError:
            continue

        decision = classify_trend(features)
        row_buffer.append(
            {
                "trade_date": trade_date.isoformat(),
                "ticker": ticker,
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "volume": float(bar["volume"]),
                "ma5": features.ma5,
                "ma20": features.ma20,
                "ma60": features.ma60,
                "slope5": features.slope5,
                "slope20": features.slope20,
                "slope60": features.slope60,
                "ma_order_code": features.ma_order_code,
                "slope_code": features.slope_code,
                **asdict(decision),
            }
        )

    result_rows = [
        row for row in row_buffer if start_date <= _parse_date(str(row["trade_date"])) <= end_date
    ]
    if not result_rows:
        raise RuntimeError(
            f"No valid trend decision rows generated for range=[{start_date}, {end_date}] after feature/classification."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{ticker}_trend_decision_1d.csv"
    fieldnames = [
        "trade_date",
        "ticker",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ma5",
        "ma20",
        "ma60",
        "slope5",
        "slope20",
        "slope60",
        "ma_order_code",
        "slope_code",
        "trend_type",
        "trend_strength",
        "action_bias",
        "buy_threshold_pct",
        "sell_threshold_pct",
        "rebound_pct",
        "budget_multiplier",
        "reason",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in result_rows:
            row["trade_date"] = _parse_date(str(row["trade_date"])).isoformat()
            writer.writerow({key: row.get(key) for key in fieldnames})

    LOGGER.info("Exported %s trend rows to %s", len(result_rows), output_path)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export daily trend decision results to CSV.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--db-path", default=str(DEFAULT_DAILY_DB_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--warmup-days", type=int, default=180)
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    export_trend_decision_csv(
        ticker=args.ticker,
        start_date=_parse_date(args.start_date),
        end_date=_parse_date(args.end_date),
        interval=args.interval,
        db_path=args.db_path,
        output_dir=args.output_dir,
        warmup_days=args.warmup_days,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

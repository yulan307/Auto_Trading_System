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
from app.trend.classifier import classify_trend
from app.trend.features import compute_ma_features


LOGGER = logging.getLogger(__name__)
DEFAULT_DAILY_DB_PATH = PROJECT_ROOT / "data" / "daily.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_WARMUP_DAYS = 180

FIELDNAMES = [
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
    "ma_state_code",
    "slope_state_code",
    "day_state_code",
    "state_seq_5d",
    "trend_type",
    "trend_strength",
    "action_bias",
    "buy_threshold_pct",
    "sell_threshold_pct",
    "rebound_pct",
    "budget_multiplier",
    "reason",
]


def _parse_date(raw: str) -> date:
    return datetime.fromisoformat(raw).date()


def _to_date(raw: Any) -> date:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    return datetime.fromisoformat(str(raw)).date()


def _default_output_path(ticker: str) -> Path:
    return DEFAULT_OUTPUT_DIR / f"{ticker}_trend_state_research_1d.csv"


def encode_ma_state_code(*, ma5: float, ma20: float, ma60: float) -> str | None:
    if ma5 > ma20 > ma60:
        return "a"
    if ma5 > ma60 > ma20:
        return "b"
    if ma20 > ma5 > ma60:
        return "c"
    if ma20 > ma60 > ma5:
        return "d"
    if ma60 > ma5 > ma20:
        return "e"
    if ma60 > ma20 > ma5:
        return "f"
    return None


def encode_slope_state_code(*, slope5: float, slope20: float, slope60: float) -> str:
    signs = (
        "+" if slope5 > 0 else "-",
        "+" if slope20 > 0 else "-",
        "+" if slope60 > 0 else "-",
    )
    mapping = {
        ("+", "+", "+"): "1",
        ("+", "+", "-"): "2",
        ("+", "-", "+"): "3",
        ("+", "-", "-"): "4",
        ("-", "+", "+"): "5",
        ("-", "+", "-"): "6",
        ("-", "-", "+"): "7",
        ("-", "-", "-"): "8",
    }
    return mapping[signs]


def build_state_seq_5d(day_state_codes: list[str | None]) -> list[str | None]:
    sequences: list[str | None] = []
    for index in range(len(day_state_codes)):
        if index < 5:
            sequences.append(None)
            continue

        previous_codes = day_state_codes[index - 5 : index]
        if any(code is None for code in previous_codes):
            sequences.append(None)
            continue

        sequences.append("".join(code for code in previous_codes if code is not None))
    return sequences


def export_trend_state_research_csv(
    *,
    ticker: str,
    start_date: date,
    end_date: date,
    interval: str = "1d",
    db_path: str | Path = DEFAULT_DAILY_DB_PATH,
    output_path: str | Path | None = None,
    warmup_days: int = DEFAULT_WARMUP_DAYS,
    provider: Any | None = None,
    source: str = "yfinance",
) -> Path:
    if interval != "1d":
        raise ValueError("export_trend_state_research_csv currently only supports interval='1d'.")
    if end_date < start_date:
        raise ValueError("end_date must be greater than or equal to start_date.")

    db_path = Path(db_path)
    output_path = Path(output_path) if output_path is not None else _default_output_path(ticker)
    warmup_start = start_date - timedelta(days=warmup_days)

    init_price_db(db_path, "daily_bars")

    provider_instance = provider or YFinanceProvider()
    LOGGER.info(
        "data_update_start ticker=%s interval=%s start=%s end=%s",
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
    LOGGER.info("data_update_done result=%s", update_result)

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
    feature_rows: list[dict[str, Any]] = []
    for bar in bars:
        closes.append(float(bar["close"]))
        trade_date = _to_date(bar["datetime"])

        try:
            features = compute_ma_features(ticker=ticker, trade_date=trade_date, closes=closes)
        except ValueError:
            continue

        feature_rows.append(
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
                "_features": features,
            }
        )

    if not feature_rows:
        raise RuntimeError(
            f"No valid research rows generated for ticker={ticker} in range=[{warmup_start}, {end_date}]"
        )
    LOGGER.info("feature_compute_done rows=%s", len(feature_rows))

    for row in feature_rows:
        ma_state_code = encode_ma_state_code(ma5=row["ma5"], ma20=row["ma20"], ma60=row["ma60"])
        slope_state_code = encode_slope_state_code(
            slope5=row["slope5"],
            slope20=row["slope20"],
            slope60=row["slope60"],
        )
        row["ma_state_code"] = ma_state_code
        row["slope_state_code"] = slope_state_code
        row["day_state_code"] = (
            f"{ma_state_code}{slope_state_code}" if ma_state_code is not None else None
        )
    LOGGER.info("state_encode_done rows=%s", len(feature_rows))

    sequences = build_state_seq_5d([row["day_state_code"] for row in feature_rows])
    for row, sequence in zip(feature_rows, sequences, strict=True):
        row["state_seq_5d"] = sequence
    LOGGER.info("state_seq_done rows=%s", len(feature_rows))

    for row in feature_rows:
        decision = classify_trend(row["_features"])
        row.update(asdict(decision))
        row.pop("_features", None)
    LOGGER.info("trend_classify_done rows=%s", len(feature_rows))

    result_rows = [
        row for row in feature_rows if start_date <= _parse_date(str(row["trade_date"])) <= end_date
    ]
    if not result_rows:
        raise RuntimeError(
            f"No valid research rows generated for range=[{start_date}, {end_date}] after filtering."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in result_rows:
            writer.writerow({key: row.get(key) for key in FIELDNAMES})

    LOGGER.info("csv_export_done rows=%s output=%s", len(result_rows), output_path)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export daily trend, state codes, and prior-5-day state sequences to CSV."
    )
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--start", "--start-date", dest="start_date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", "--end-date", dest="end_date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--db", "--db-path", dest="db_path", default=str(DEFAULT_DAILY_DB_PATH))
    parser.add_argument("--output", dest="output_path", default=None)
    parser.add_argument("--warmup-days", type=int, default=DEFAULT_WARMUP_DAYS)
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    export_trend_state_research_csv(
        ticker=args.ticker,
        start_date=_parse_date(args.start_date),
        end_date=_parse_date(args.end_date),
        interval=args.interval,
        db_path=args.db_path,
        output_path=args.output_path,
        warmup_days=args.warmup_days,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import logging

from app.trend.features import (
    DEFAULT_DAILY_DB_PATH,
    DEFAULT_FEATURE_DB_PATH,
    DEFAULT_OUTPUT_CSV_DIR,
    DEFAULT_TABLE_NAME,
    OUTPUT_COLUMNS,
    PERCENTILE_HISTORY_WINDOW,
    TrendFeatureRunResult,
    _compute_linear_slope,
    compute_fetch_start_date,
    compute_signed_rolling_percentile,
    compute_trend_features_for_ticker,
    run_trend_feature_pipeline,
)


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update the shared feature store and export CSV research slices for the requested tickers."
    )
    parser.add_argument("--tickers", nargs="+", required=True, help="One or more ticker symbols.")
    parser.add_argument("--start-date", required=True, help="Research output start date in YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Research output end date in YYYY-MM-DD.")
    parser.add_argument("--daily-db-path", default=str(DEFAULT_DAILY_DB_PATH))
    parser.add_argument("--feature-db-path", default=str(DEFAULT_FEATURE_DB_PATH))
    parser.add_argument("--output-csv-dir", default=str(DEFAULT_OUTPUT_CSV_DIR))
    parser.add_argument("--history-window", type=int, default=PERCENTILE_HISTORY_WINDOW)
    parser.add_argument("--table-name", default=DEFAULT_TABLE_NAME)
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    result = run_trend_feature_pipeline(
        tickers=args.tickers,
        start_date=args.start_date,
        end_date=args.end_date,
        daily_db_path=args.daily_db_path,
        feature_db_path=args.feature_db_path,
        output_csv_dir=args.output_csv_dir,
        history_window=args.history_window,
        table_name=args.table_name,
    )

    if result.failed_tickers:
        LOGGER.warning("partial_failures failed_tickers=%s", result.failed_tickers)
        return 1
    return 0


__all__ = [
    "OUTPUT_COLUMNS",
    "TrendFeatureRunResult",
    "_compute_linear_slope",
    "build_parser",
    "compute_fetch_start_date",
    "compute_signed_rolling_percentile",
    "compute_trend_features_for_ticker",
    "main",
    "run_trend_feature_pipeline",
]


if __name__ == "__main__":
    raise SystemExit(main())

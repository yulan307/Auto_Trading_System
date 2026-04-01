from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.providers.yfinance_provider import YFinanceProvider
from app.data.repository import init_price_db, load_bars
from app.data.updater import update_symbol_data
from app.trend.features import compute_ma_features


LOGGER = logging.getLogger(__name__)
DEFAULT_DAILY_DB_PATH = PROJECT_ROOT / "data" / "raw" / "daily.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "trend_zone_rebound"
DEFAULT_WARMUP_DAYS = 200
DEFAULT_FORWARD_HORIZONS = (1, 3, 5, 10, 20)

ZONE_COMBOS = ("+++", "++-", "+-+", "+--", "-++", "-+-", "--+", "---")
REBOUND_COMBOS = ("++", "+-", "-+", "--")

DAILY_FIELDNAMES = [
    "ticker",
    "date",
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
    "day_state_code",
    "state_seq_5d",
    "spread2060",
    "d_spread2060",
    "slope60_sign",
    "spread2060_sign",
    "d_spread2060_sign",
    "zone_combo_3",
    "dev_low5",
    "d_dev_low5",
    "dev_low20",
    "dev_low60",
    "dev_low5_sign",
    "d_dev_low5_sign",
    "rebound_base_combo_2",
    "dev_close5",
    "dev_close20",
    "dev_close60",
    "day_ret",
    "range_pct",
    "vol_ma20",
    "vol_ratio20",
    "fwd_ret_1d",
    "fwd_ret_3d",
    "fwd_ret_5d",
    "fwd_ret_10d",
    "fwd_ret_20d",
    "valid_row_flag",
]

SUMMARY_FIELDNAMES = [
    "ticker",
    "start_date",
    "end_date",
    "row_count",
    "valid_row_count",
    "combo_+++_count",
    "combo_++-_count",
    "combo_+-+_count",
    "combo_+--_count",
    "combo_-++_count",
    "combo_-+-_count",
    "combo_--+_count",
    "combo_---_count",
    "combo_zero_sign_count",
    "rebound_combo_++_count",
    "rebound_combo_+-_count",
    "rebound_combo_-+_count",
    "rebound_combo_--_count",
    "rebound_combo_zero_sign_count",
]


def _parse_date(raw: str) -> date:
    return datetime.fromisoformat(raw).date()


def _to_date(raw: Any) -> date:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    return datetime.fromisoformat(str(raw)).date()


def _sign_symbol(value: Any) -> str | pd._libs.missing.NAType:
    if pd.isna(value):
        return pd.NA
    if float(value) > 0:
        return "+"
    if float(value) < 0:
        return "-"
    return "0"


def _combine_signs(values: Iterable[Any]) -> str | pd._libs.missing.NAType:
    parts = list(values)
    if any(pd.isna(part) for part in parts):
        return pd.NA
    return "".join(str(part) for part in parts)


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    safe_denominator = denominator.where(denominator != 0)
    return numerator / safe_denominator


def _ensure_daily_column_order(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in DAILY_FIELDNAMES:
        if column not in result.columns:
            result[column] = pd.NA
    return result[DAILY_FIELDNAMES]


def load_or_update_daily_data(
    ticker: str,
    start_date: date,
    end_date: date,
    *,
    interval: str = "1d",
    db_path: str | Path = DEFAULT_DAILY_DB_PATH,
    warmup_days: int = DEFAULT_WARMUP_DAYS,
    provider: Any | None = None,
    source: str = "yfinance",
    auto_update_db: bool = True,
) -> pd.DataFrame:
    if interval != "1d":
        raise ValueError("load_or_update_daily_data currently only supports interval='1d'.")
    if end_date < start_date:
        raise ValueError("end_date must be greater than or equal to start_date.")

    db_path = Path(db_path)
    warmup_start = start_date - timedelta(days=warmup_days)

    init_price_db(db_path, "daily_bars")

    if auto_update_db:
        provider_instance = provider or YFinanceProvider()
        LOGGER.info(
            "Updating daily bars ticker=%s interval=%s warmup_start=%s end_date=%s",
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
            f"No bars found in daily.db. ticker={ticker}, interval={interval}, "
            f"range=[{warmup_start}, {end_date}]"
        )

    frame = pd.DataFrame(bars)
    frame["date"] = pd.to_datetime(frame["datetime"]).dt.date
    frame = frame.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    return frame[["date", "open", "high", "low", "close", "volume"]].copy()


def compute_standard_trend_features(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    result = df.copy()
    result["ticker"] = ticker
    result["ma5"] = result["close"].rolling(window=5).mean()
    result["ma20"] = result["close"].rolling(window=20).mean()
    result["ma60"] = result["close"].rolling(window=60).mean()
    result["slope5"] = pd.NA
    result["slope20"] = pd.NA
    result["slope60"] = pd.NA
    result["ma_order_code"] = pd.NA
    result["slope_code"] = pd.NA
    result["day_state_code"] = pd.NA
    result["state_seq_5d"] = pd.NA

    closes: list[float] = []
    for index, row in result.iterrows():
        closes.append(float(row["close"]))
        try:
            features = compute_ma_features(ticker=ticker, trade_date=_to_date(row["date"]), closes=closes)
        except ValueError:
            continue

        result.at[index, "ma5"] = features.ma5
        result.at[index, "ma20"] = features.ma20
        result.at[index, "ma60"] = features.ma60
        result.at[index, "slope5"] = features.slope5
        result.at[index, "slope20"] = features.slope20
        result.at[index, "slope60"] = features.slope60
        result.at[index, "ma_order_code"] = features.ma_order_code
        result.at[index, "slope_code"] = features.slope_code

    return result


def compute_zone_combo_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["spread2060"] = _safe_divide(
        pd.to_numeric(result["ma20"], errors="coerce") - pd.to_numeric(result["ma60"], errors="coerce"),
        pd.to_numeric(result["ma60"], errors="coerce"),
    )
    result["d_spread2060"] = result["spread2060"].diff()
    result["slope60_sign"] = result["slope60"].map(_sign_symbol)
    result["spread2060_sign"] = result["spread2060"].map(_sign_symbol)
    result["d_spread2060_sign"] = result["d_spread2060"].map(_sign_symbol)
    result["zone_combo_3"] = result.apply(
        lambda row: _combine_signs(
            [row["slope60_sign"], row["spread2060_sign"], row["d_spread2060_sign"]]
        ),
        axis=1,
    )
    return result


def compute_rebound_base_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    ma5 = pd.to_numeric(result["ma5"], errors="coerce")
    ma20 = pd.to_numeric(result["ma20"], errors="coerce")
    ma60 = pd.to_numeric(result["ma60"], errors="coerce")
    close = pd.to_numeric(result["close"], errors="coerce")
    low = pd.to_numeric(result["low"], errors="coerce")
    high = pd.to_numeric(result["high"], errors="coerce")
    volume = pd.to_numeric(result["volume"], errors="coerce")

    result["dev_low5"] = _safe_divide(low, ma5) - 1
    result["d_dev_low5"] = result["dev_low5"].diff()
    result["dev_low20"] = _safe_divide(low, ma20) - 1
    result["dev_low60"] = _safe_divide(low, ma60) - 1
    result["dev_low5_sign"] = result["dev_low5"].map(_sign_symbol)
    result["d_dev_low5_sign"] = result["d_dev_low5"].map(_sign_symbol)
    result["rebound_base_combo_2"] = result.apply(
        lambda row: _combine_signs([row["dev_low5_sign"], row["d_dev_low5_sign"]]),
        axis=1,
    )

    result["dev_close5"] = _safe_divide(close, ma5) - 1
    result["dev_close20"] = _safe_divide(close, ma20) - 1
    result["dev_close60"] = _safe_divide(close, ma60) - 1
    result["day_ret"] = close.pct_change()
    result["range_pct"] = _safe_divide(high - low, close.shift(1))
    result["vol_ma20"] = volume.rolling(window=20).mean()
    result["vol_ratio20"] = _safe_divide(volume, result["vol_ma20"])

    valid_columns = ["ma60", "spread2060", "d_spread2060", "dev_low5", "d_dev_low5"]
    result["valid_row_flag"] = result[valid_columns].notna().all(axis=1).astype(int)
    return result


def compute_forward_returns(df: pd.DataFrame, horizons: tuple[int, ...] = DEFAULT_FORWARD_HORIZONS) -> pd.DataFrame:
    result = df.copy()
    close = pd.to_numeric(result["close"], errors="coerce")
    for horizon in horizons:
        result[f"fwd_ret_{horizon}d"] = _safe_divide(close.shift(-horizon), close) - 1
    return result


def build_single_ticker_feature_table(
    ticker: str,
    start_date: date,
    end_date: date,
    *,
    interval: str = "1d",
    db_path: str | Path = DEFAULT_DAILY_DB_PATH,
    warmup_days: int = DEFAULT_WARMUP_DAYS,
    provider: Any | None = None,
    source: str = "yfinance",
    auto_update_db: bool = True,
) -> pd.DataFrame:
    result = load_or_update_daily_data(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        db_path=db_path,
        warmup_days=warmup_days,
        provider=provider,
        source=source,
        auto_update_db=auto_update_db,
    )
    result = compute_standard_trend_features(result, ticker=ticker)
    result = compute_zone_combo_features(result)
    result = compute_rebound_base_features(result)
    result = compute_forward_returns(result)
    result = result[(result["date"] >= start_date) & (result["date"] <= end_date)].copy()
    if result.empty:
        raise RuntimeError(f"No research rows generated for ticker={ticker} in range=[{start_date}, {end_date}].")

    result["date"] = result["date"].map(lambda value: value.isoformat())
    return _ensure_daily_column_order(result)


def build_summary_table(daily_df: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if daily_df.empty:
        return pd.DataFrame(columns=SUMMARY_FIELDNAMES)

    for ticker, frame in daily_df.groupby("ticker", sort=True):
        valid_frame = frame[frame["valid_row_flag"] == 1].copy()
        row: dict[str, Any] = {
            "ticker": ticker,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "row_count": int(len(frame)),
            "valid_row_count": int(valid_frame["valid_row_flag"].sum()),
        }

        for combo in ZONE_COMBOS:
            row[f"combo_{combo}_count"] = int((valid_frame["zone_combo_3"] == combo).sum())
        row["combo_zero_sign_count"] = int(
            valid_frame["zone_combo_3"].astype("string").str.contains("0", na=False).sum()
        )

        for combo in REBOUND_COMBOS:
            row[f"rebound_combo_{combo}_count"] = int((valid_frame["rebound_base_combo_2"] == combo).sum())
        row["rebound_combo_zero_sign_count"] = int(
            valid_frame["rebound_base_combo_2"].astype("string").str.contains("0", na=False).sum()
        )

        rows.append(row)

    summary_df = pd.DataFrame(rows)
    for column in SUMMARY_FIELDNAMES:
        if column not in summary_df.columns:
            summary_df[column] = pd.NA
    return summary_df[SUMMARY_FIELDNAMES]


def build_multi_ticker_feature_tables(
    tickers: list[str],
    start_date: date,
    end_date: date,
    *,
    interval: str = "1d",
    db_path: str | Path = DEFAULT_DAILY_DB_PATH,
    warmup_days: int = DEFAULT_WARMUP_DAYS,
    provider: Any | None = None,
    source: str = "yfinance",
    auto_update_db: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_tables = [
        build_single_ticker_feature_table(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            db_path=db_path,
            warmup_days=warmup_days,
            provider=provider,
            source=source,
            auto_update_db=auto_update_db,
        )
        for ticker in tickers
    ]

    daily_df = pd.concat(daily_tables, ignore_index=True)
    summary_df = build_summary_table(daily_df, start_date=start_date, end_date=end_date)
    return daily_df, summary_df


def export_feature_tables(
    daily_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    daily_path = output_dir / "trend_zone_rebound_daily.csv"
    summary_path = output_dir / "trend_zone_rebound_summary.csv"

    daily_df.to_csv(daily_path, index=False, encoding="utf-8-sig")
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    return daily_path, summary_path


def export_trend_zone_rebound_features(
    *,
    tickers: list[str],
    start_date: date,
    end_date: date,
    interval: str = "1d",
    db_path: str | Path = DEFAULT_DAILY_DB_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    warmup_days: int = DEFAULT_WARMUP_DAYS,
    provider: Any | None = None,
    source: str = "yfinance",
    auto_update_db: bool = True,
) -> tuple[Path, Path]:
    daily_df, summary_df = build_multi_ticker_feature_tables(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        db_path=db_path,
        warmup_days=warmup_days,
        provider=provider,
        source=source,
        auto_update_db=auto_update_db,
    )
    return export_feature_tables(daily_df=daily_df, summary_df=summary_df, output_dir=output_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export multi-ticker trend zone rebound research CSVs.")
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--db-path", default=str(DEFAULT_DAILY_DB_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--warmup-days", type=int, default=DEFAULT_WARMUP_DAYS)
    parser.add_argument("--source", default="yfinance")

    auto_update_group = parser.add_mutually_exclusive_group()
    auto_update_group.add_argument(
        "--auto-update-db",
        dest="auto_update_db",
        action="store_true",
        help="Fetch and save missing daily bars before building the research tables.",
    )
    auto_update_group.add_argument(
        "--no-auto-update-db",
        dest="auto_update_db",
        action="store_false",
        help="Use only bars that already exist in the local daily DB.",
    )
    parser.set_defaults(auto_update_db=True)
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    export_trend_zone_rebound_features(
        tickers=args.tickers,
        start_date=_parse_date(args.start),
        end_date=_parse_date(args.end),
        interval=args.interval,
        db_path=args.db_path,
        output_dir=args.output_dir,
        warmup_days=args.warmup_days,
        source=args.source,
        auto_update_db=args.auto_update_db,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

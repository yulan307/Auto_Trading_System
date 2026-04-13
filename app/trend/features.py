from __future__ import annotations

import logging
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from app.data.db import connect_sqlite, init_price_db
from app.data.repository import load_bars
from app.data.updater import update_daily_db


LOGGER = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DAILY_DB_PATH = PROJECT_ROOT / "data" / "daily.db"
DEFAULT_FEATURE_DB_PATH = PROJECT_ROOT / "data" / "feature.db"
DEFAULT_OUTPUT_CSV_DIR = PROJECT_ROOT / "data" / "processed" / "features"
DEFAULT_TABLE_NAME = "trend_features_daily"

PERCENTILE_CALENDAR_WINDOW = 365
DRV_WINDOWS: tuple[int, ...] = (2, 5)
REQUIRED_PRICE_COLUMNS = (
    "datetime",
    "interval",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
    "update_time",
)
BASE_OUTPUT_COLUMNS = (
    "ticker",
    "datetime",
    "interval",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
    "update_time",
)

HIST_WINDOW_SPECS: tuple[tuple[str, int], ...] = (("w", 5), ("m", 20), ("q", 60), ("h", 120))
FUT_WINDOW_SPECS: tuple[tuple[str, int, int], ...] = (("w", 5, 2), ("m", 20, 9))
SPREAD_PAIRS: tuple[tuple[str, str], ...] = (("w", "m"), ("m", "q"), ("q", "h"))
FUT_SPREAD_PAIRS: tuple[tuple[str, str], ...] = (("w", "m"),)

HIST_WINDOW_LABELS = tuple(label for label, _ in HIST_WINDOW_SPECS)
FUT_WINDOW_LABELS = tuple(label for label, _, _ in FUT_WINDOW_SPECS)

HIST_REFERENCE_COLUMNS = ("hist_open", "hist_high", "hist_low", "hist_close")

HIST_MA_COLUMNS = tuple(f"hist_ma_{label}" for label in HIST_WINDOW_LABELS)
HIST_SLOPE_COLUMNS = tuple(f"hist_slope_{label}" for label in HIST_WINDOW_LABELS)
HIST_LOW_DEV_COLUMNS = tuple(f"hist_low_dev_{label}" for label in HIST_WINDOW_LABELS)
HIST_HIGH_DEV_COLUMNS = tuple(f"hist_high_dev_{label}" for label in HIST_WINDOW_LABELS)
HIST_SPREAD_COLUMNS = tuple(f"hist_spread_{left}_{right}" for left, right in SPREAD_PAIRS)

HIST_SLOPE_DRV_COLUMNS = tuple(
    f"hist_slope_drv{drv}_{label}" for drv in DRV_WINDOWS for label in HIST_WINDOW_LABELS
)
HIST_SPREAD_DRV_COLUMNS = tuple(
    f"hist_spread_drv{drv}_{left}_{right}" for drv in DRV_WINDOWS for left, right in SPREAD_PAIRS
)
HIST_LOW_DEV_DRV_COLUMNS = tuple(
    f"hist_low_dev_drv{drv}_{label}" for drv in DRV_WINDOWS for label in HIST_WINDOW_LABELS
)
HIST_HIGH_DEV_DRV_COLUMNS = tuple(
    f"hist_high_dev_drv{drv}_{label}" for drv in DRV_WINDOWS for label in HIST_WINDOW_LABELS
)
HIST_LOW_DEV_SLOPE_COLUMNS = tuple(f"hist_low_dev_slope_{label}" for label in HIST_WINDOW_LABELS)
HIST_HIGH_DEV_SLOPE_COLUMNS = tuple(f"hist_high_dev_slope_{label}" for label in HIST_WINDOW_LABELS)
HIST_LOW_DEV_SLOPE_DRV_COLUMNS = tuple(
    f"hist_low_dev_slope_drv{drv}_{label}" for drv in DRV_WINDOWS for label in HIST_WINDOW_LABELS
)
HIST_HIGH_DEV_SLOPE_DRV_COLUMNS = tuple(
    f"hist_high_dev_slope_drv{drv}_{label}" for drv in DRV_WINDOWS for label in HIST_WINDOW_LABELS
)

FUT_MA_COLUMNS = tuple(f"fut_ma_{label}" for label in FUT_WINDOW_LABELS)
FUT_SLOPE_COLUMNS = tuple(f"fut_slope_{label}" for label in FUT_WINDOW_LABELS)
FUT_LOW_DEV_COLUMNS = tuple(f"fut_low_dev_{label}" for label in FUT_WINDOW_LABELS)
FUT_HIGH_DEV_COLUMNS = tuple(f"fut_high_dev_{label}" for label in FUT_WINDOW_LABELS)
FUT_SPREAD_COLUMNS = tuple(f"fut_spread_{left}_{right}" for left, right in FUT_SPREAD_PAIRS)

FUT_SLOPE_DRV_COLUMNS = tuple(
    f"fut_slope_drv{drv}_{label}" for drv in DRV_WINDOWS for label in FUT_WINDOW_LABELS
)
FUT_SPREAD_DRV_COLUMNS = tuple(
    f"fut_spread_drv{drv}_{left}_{right}" for drv in DRV_WINDOWS for left, right in FUT_SPREAD_PAIRS
)
FUT_LOW_DEV_DRV_COLUMNS = tuple(
    f"fut_low_dev_drv{drv}_{label}" for drv in DRV_WINDOWS for label in FUT_WINDOW_LABELS
)
FUT_HIGH_DEV_DRV_COLUMNS = tuple(
    f"fut_high_dev_drv{drv}_{label}" for drv in DRV_WINDOWS for label in FUT_WINDOW_LABELS
)
FUT_LOW_DEV_SLOPE_COLUMNS = tuple(f"fut_low_dev_slope_{label}" for label in FUT_WINDOW_LABELS)
FUT_HIGH_DEV_SLOPE_COLUMNS = tuple(f"fut_high_dev_slope_{label}" for label in FUT_WINDOW_LABELS)
FUT_LOW_DEV_SLOPE_DRV_COLUMNS = tuple(
    f"fut_low_dev_slope_drv{drv}_{label}" for drv in DRV_WINDOWS for label in FUT_WINDOW_LABELS
)
FUT_HIGH_DEV_SLOPE_DRV_COLUMNS = tuple(
    f"fut_high_dev_slope_drv{drv}_{label}" for drv in DRV_WINDOWS for label in FUT_WINDOW_LABELS
)

HIST_PERCENTILE_SOURCE_TO_OUTPUT = {
    **{f"hist_slope_{label}": f"hist_slope_pct_{label}" for label in HIST_WINDOW_LABELS},
    **{
        f"hist_slope_drv{drv}_{label}": f"hist_slope_drv{drv}_pct_{label}"
        for drv in DRV_WINDOWS
        for label in HIST_WINDOW_LABELS
    },
    **{f"hist_spread_{left}_{right}": f"hist_spread_pct_{left}_{right}" for left, right in SPREAD_PAIRS},
    **{
        f"hist_spread_drv{drv}_{left}_{right}": f"hist_spread_drv{drv}_pct_{left}_{right}"
        for drv in DRV_WINDOWS
        for left, right in SPREAD_PAIRS
    },
    **{f"hist_low_dev_{label}": f"hist_low_dev_pct_{label}" for label in HIST_WINDOW_LABELS},
    **{
        f"hist_low_dev_drv{drv}_{label}": f"hist_low_dev_drv{drv}_pct_{label}"
        for drv in DRV_WINDOWS
        for label in HIST_WINDOW_LABELS
    },
    **{f"hist_high_dev_{label}": f"hist_high_dev_pct_{label}" for label in HIST_WINDOW_LABELS},
    **{
        f"hist_high_dev_drv{drv}_{label}": f"hist_high_dev_drv{drv}_pct_{label}"
        for drv in DRV_WINDOWS
        for label in HIST_WINDOW_LABELS
    },
    **{
        f"hist_low_dev_slope_{label}": f"hist_low_dev_slope_pct_{label}" for label in HIST_WINDOW_LABELS
    },
    **{
        f"hist_low_dev_slope_drv{drv}_{label}": f"hist_low_dev_slope_drv{drv}_pct_{label}"
        for drv in DRV_WINDOWS
        for label in HIST_WINDOW_LABELS
    },
    **{
        f"hist_high_dev_slope_{label}": f"hist_high_dev_slope_pct_{label}" for label in HIST_WINDOW_LABELS
    },
    **{
        f"hist_high_dev_slope_drv{drv}_{label}": f"hist_high_dev_slope_drv{drv}_pct_{label}"
        for drv in DRV_WINDOWS
        for label in HIST_WINDOW_LABELS
    },
}
FUT_PERCENTILE_SOURCE_TO_OUTPUT = {
    **{f"fut_slope_{label}": f"fut_slope_pct_{label}" for label in FUT_WINDOW_LABELS},
    **{
        f"fut_slope_drv{drv}_{label}": f"fut_slope_drv{drv}_pct_{label}"
        for drv in DRV_WINDOWS
        for label in FUT_WINDOW_LABELS
    },
    **{f"fut_spread_{left}_{right}": f"fut_spread_pct_{left}_{right}" for left, right in FUT_SPREAD_PAIRS},
    **{
        f"fut_spread_drv{drv}_{left}_{right}": f"fut_spread_drv{drv}_pct_{left}_{right}"
        for drv in DRV_WINDOWS
        for left, right in FUT_SPREAD_PAIRS
    },
    **{f"fut_low_dev_{label}": f"fut_low_dev_pct_{label}" for label in FUT_WINDOW_LABELS},
    **{
        f"fut_low_dev_drv{drv}_{label}": f"fut_low_dev_drv{drv}_pct_{label}"
        for drv in DRV_WINDOWS
        for label in FUT_WINDOW_LABELS
    },
    **{f"fut_high_dev_{label}": f"fut_high_dev_pct_{label}" for label in FUT_WINDOW_LABELS},
    **{
        f"fut_high_dev_drv{drv}_{label}": f"fut_high_dev_drv{drv}_pct_{label}"
        for drv in DRV_WINDOWS
        for label in FUT_WINDOW_LABELS
    },
    **{f"fut_low_dev_slope_{label}": f"fut_low_dev_slope_pct_{label}" for label in FUT_WINDOW_LABELS},
    **{
        f"fut_low_dev_slope_drv{drv}_{label}": f"fut_low_dev_slope_drv{drv}_pct_{label}"
        for drv in DRV_WINDOWS
        for label in FUT_WINDOW_LABELS
    },
    **{f"fut_high_dev_slope_{label}": f"fut_high_dev_slope_pct_{label}" for label in FUT_WINDOW_LABELS},
    **{
        f"fut_high_dev_slope_drv{drv}_{label}": f"fut_high_dev_slope_drv{drv}_pct_{label}"
        for drv in DRV_WINDOWS
        for label in FUT_WINDOW_LABELS
    },
}
FEATURE_VALUE_TO_PERCENTILE_COLUMN = {**HIST_PERCENTILE_SOURCE_TO_OUTPUT, **FUT_PERCENTILE_SOURCE_TO_OUTPUT}

HIST_PERCENTILE_COLUMNS = tuple(HIST_PERCENTILE_SOURCE_TO_OUTPUT.values())
FUT_PERCENTILE_COLUMNS = tuple(FUT_PERCENTILE_SOURCE_TO_OUTPUT.values())

OUTPUT_COLUMNS = (
    *BASE_OUTPUT_COLUMNS,
    *HIST_REFERENCE_COLUMNS,
    *HIST_MA_COLUMNS,
    *HIST_SLOPE_COLUMNS,
    *HIST_LOW_DEV_COLUMNS,
    *HIST_HIGH_DEV_COLUMNS,
    *HIST_SPREAD_COLUMNS,
    *HIST_SLOPE_DRV_COLUMNS,
    *HIST_SPREAD_DRV_COLUMNS,
    *HIST_LOW_DEV_DRV_COLUMNS,
    *HIST_HIGH_DEV_DRV_COLUMNS,
    *HIST_LOW_DEV_SLOPE_COLUMNS,
    *HIST_HIGH_DEV_SLOPE_COLUMNS,
    *HIST_LOW_DEV_SLOPE_DRV_COLUMNS,
    *HIST_HIGH_DEV_SLOPE_DRV_COLUMNS,
    *HIST_PERCENTILE_COLUMNS,
    *FUT_MA_COLUMNS,
    *FUT_SLOPE_COLUMNS,
    *FUT_LOW_DEV_COLUMNS,
    *FUT_HIGH_DEV_COLUMNS,
    *FUT_SPREAD_COLUMNS,
    *FUT_SLOPE_DRV_COLUMNS,
    *FUT_SPREAD_DRV_COLUMNS,
    *FUT_LOW_DEV_DRV_COLUMNS,
    *FUT_HIGH_DEV_DRV_COLUMNS,
    *FUT_LOW_DEV_SLOPE_COLUMNS,
    *FUT_HIGH_DEV_SLOPE_COLUMNS,
    *FUT_LOW_DEV_SLOPE_DRV_COLUMNS,
    *FUT_HIGH_DEV_SLOPE_DRV_COLUMNS,
    *FUT_PERCENTILE_COLUMNS,
)

TEXT_OUTPUT_COLUMNS = {"ticker", "datetime", "interval", "source", "update_time"}
COLUMN_TYPE_BY_NAME = {
    column: ("TEXT" if column in TEXT_OUTPUT_COLUMNS else "REAL")
    for column in OUTPUT_COLUMNS
}

HIST_MAX_WINDOW = max(window for _, window in HIST_WINDOW_SPECS)
HIST_WARMUP_BARS = HIST_MAX_WINDOW + (HIST_MAX_WINDOW - 1)
# Bar-equivalent of the percentile calendar window, used for compute-window sizing.
_PERCENTILE_WARMUP_BARS = math.ceil(PERCENTILE_CALENDAR_WINDOW * 5 / 7)
TOTAL_WARMUP_BARS = HIST_WARMUP_BARS + _PERCENTILE_WARMUP_BARS
FUTURE_BACKFILL_BARS = max(right_offset for _, _, right_offset in FUT_WINDOW_SPECS)
FUTURE_CONTEXT_CALENDAR_DAYS = 31


@dataclass(slots=True)
class TrendFeatureRunResult:
    combined_df: pd.DataFrame
    csv_paths: list[Path]
    feature_rows_loaded: int
    failed_tickers: list[str]


def _parse_date(raw: str) -> date:
    return datetime.fromisoformat(raw).date()


def _coerce_date(value: str | date | datetime) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return _parse_date(str(value))


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    safe_denominator = denominator.where(denominator != 0)
    return numerator / safe_denominator


def _validate_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise ValueError(f"Invalid SQLite identifier: {identifier!r}")
    return identifier


def _normalize_datetime_column(series: pd.Series) -> pd.Series:
    timestamps = pd.to_datetime(series, errors="coerce")
    if timestamps.isna().any():
        raise ValueError("Found invalid datetime values while loading daily bars.")
    return timestamps.dt.strftime("%Y-%m-%d")


def _prepare_price_frame(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    missing = [column for column in REQUIRED_PRICE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Ticker {ticker} missing required columns: {missing}")

    result = frame.loc[:, list(REQUIRED_PRICE_COLUMNS)].copy()
    result["datetime"] = _normalize_datetime_column(result["datetime"])
    result = result.sort_values("datetime").drop_duplicates(subset=["datetime"], keep="last").reset_index(drop=True)

    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
        if result[column].isna().any():
            raise ValueError(f"Ticker {ticker} has non-numeric values in column {column!r}.")

    result["interval"] = result["interval"].fillna("1d").astype(str)
    result["source"] = result["source"].fillna("unknown").astype(str)
    result["update_time"] = result["update_time"].fillna("").astype(str)
    result.insert(0, "ticker", ticker)
    return result


def _compute_linear_slope(series: np.ndarray) -> float:
    if np.isnan(series).any():
        return float("nan")
    window = len(series)
    x = np.arange(1, window + 1, dtype=float)
    x_centered = x - x.mean()
    y_centered = series - series.mean()
    denominator = np.square(x_centered).sum()
    if denominator == 0:
        return float("nan")
    return float((x_centered * y_centered).sum() / denominator)


def _rolling_slope(series: pd.Series, window: int) -> pd.Series:
    numeric_series = pd.to_numeric(series, errors="coerce")
    return numeric_series.rolling(window=window, min_periods=window).apply(_compute_linear_slope, raw=True)


def _rolling_mean(series: pd.Series, window: int) -> pd.Series:
    numeric_series = pd.to_numeric(series, errors="coerce")
    return numeric_series.rolling(window=window, min_periods=window).mean()


def _centered_rolling_mean(series: pd.Series, window: int, right_offset: int) -> pd.Series:
    return _rolling_mean(series, window).shift(-right_offset)


def _centered_rolling_slope(series: pd.Series, window: int, right_offset: int) -> pd.Series:
    return _rolling_slope(series, window).shift(-right_offset)


def compute_hist_warmup_bars() -> int:
    return HIST_WARMUP_BARS


def compute_fetch_start_date(
    start_date: str | date | datetime,
) -> str:
    start = _coerce_date(start_date)
    calendar_lookback_days = math.ceil(TOTAL_WARMUP_BARS * 7 / 5) + 31
    return (start - timedelta(days=calendar_lookback_days)).isoformat()


def _load_daily_frame(
    *,
    ticker: str,
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    daily_db_path: str | Path = DEFAULT_DAILY_DB_PATH,
) -> pd.DataFrame:
    bars = load_bars(
        db_path=daily_db_path,
        table_name="daily_bars",
        ticker=ticker,
        interval="1d",
        start_date=_coerce_date(start_date).isoformat(),
        end_date=_coerce_date(end_date).isoformat(),
    )
    if not bars:
        return pd.DataFrame(columns=BASE_OUTPUT_COLUMNS)
    return _prepare_price_frame(pd.DataFrame(bars), ticker=ticker)


def load_daily_data_for_feature_research(
    *,
    ticker: str,
    fetch_start_date: str | date | datetime,
    end_date: str | date | datetime,
    daily_db_path: str | Path = DEFAULT_DAILY_DB_PATH,
    use_update: bool = False,
) -> pd.DataFrame:
    fetch_start = _coerce_date(fetch_start_date)
    end = _coerce_date(end_date)
    if end < fetch_start:
        raise ValueError("end_date must be greater than or equal to fetch_start_date.")

    init_price_db(daily_db_path, "daily_bars")

    if use_update:
        update_daily_db(
            ticker=ticker,
            start_date=fetch_start,
            end_date=end,
            db_path=daily_db_path,
        )

    prepared = _load_daily_frame(
        ticker=ticker,
        start_date=fetch_start,
        end_date=end,
        daily_db_path=daily_db_path,
    )
    if prepared.empty:
        raise RuntimeError(
            f"No daily bars found for ticker={ticker} in range=[{fetch_start.isoformat()}, {end.isoformat()}]."
        )

    LOGGER.info(
        "data_load_done ticker=%s fetch_start=%s end=%s rows=%s",
        ticker,
        fetch_start.isoformat(),
        end.isoformat(),
        len(prepared),
    )
    return prepared


def build_hist_reference_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for field in ("open", "high", "low", "close"):
        result[f"hist_{field}"] = pd.to_numeric(result[field], errors="coerce").shift(1)
    return result


def compute_hist_ma_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    hist_close = pd.to_numeric(result["hist_close"], errors="coerce")
    for label, window in HIST_WINDOW_SPECS:
        result[f"hist_ma_{label}"] = _rolling_mean(hist_close, window)
    return result


def compute_hist_slope_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    hist_close = pd.to_numeric(result["hist_close"], errors="coerce")
    for label, window in HIST_WINDOW_SPECS:
        result[f"hist_slope_{label}"] = _rolling_slope(hist_close, window)
    return result


def compute_hist_dev_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    hist_low = pd.to_numeric(result["hist_low"], errors="coerce")
    hist_high = pd.to_numeric(result["hist_high"], errors="coerce")
    for label in HIST_WINDOW_LABELS:
        hist_ma = pd.to_numeric(result[f"hist_ma_{label}"], errors="coerce")
        result[f"hist_low_dev_{label}"] = _safe_divide(hist_low, hist_ma) - 1.0
        result[f"hist_high_dev_{label}"] = _safe_divide(hist_high, hist_ma) - 1.0
    return result


def _add_drv_columns(df: pd.DataFrame, source_columns: Sequence[str], target_name_builder) -> pd.DataFrame:
    result = df.copy()
    for source_column in source_columns:
        source_series = pd.to_numeric(result[source_column], errors="coerce")
        for drv in DRV_WINDOWS:
            result[target_name_builder(source_column, drv)] = _rolling_slope(source_series, drv)
    return result


def compute_hist_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    for left, right in SPREAD_PAIRS:
        left_ma = pd.to_numeric(result[f"hist_ma_{left}"], errors="coerce")
        right_ma = pd.to_numeric(result[f"hist_ma_{right}"], errors="coerce")
        result[f"hist_spread_{left}_{right}"] = _safe_divide(left_ma, right_ma) - 1.0

    result = _add_drv_columns(
        result,
        HIST_SLOPE_COLUMNS,
        lambda source_column, drv: source_column.replace("hist_slope_", f"hist_slope_drv{drv}_"),
    )
    result = _add_drv_columns(
        result,
        HIST_SPREAD_COLUMNS,
        lambda source_column, drv: source_column.replace("hist_spread_", f"hist_spread_drv{drv}_"),
    )
    result = _add_drv_columns(
        result,
        HIST_LOW_DEV_COLUMNS,
        lambda source_column, drv: source_column.replace("hist_low_dev_", f"hist_low_dev_drv{drv}_"),
    )
    result = _add_drv_columns(
        result,
        HIST_HIGH_DEV_COLUMNS,
        lambda source_column, drv: source_column.replace("hist_high_dev_", f"hist_high_dev_drv{drv}_"),
    )

    for label, window in HIST_WINDOW_SPECS:
        result[f"hist_low_dev_slope_{label}"] = _rolling_slope(result[f"hist_low_dev_{label}"], window)
        result[f"hist_high_dev_slope_{label}"] = _rolling_slope(result[f"hist_high_dev_{label}"], window)

    result = _add_drv_columns(
        result,
        HIST_LOW_DEV_SLOPE_COLUMNS,
        lambda source_column, drv: source_column.replace("hist_low_dev_slope_", f"hist_low_dev_slope_drv{drv}_"),
    )
    result = _add_drv_columns(
        result,
        HIST_HIGH_DEV_SLOPE_COLUMNS,
        lambda source_column, drv: source_column.replace(
            "hist_high_dev_slope_",
            f"hist_high_dev_slope_drv{drv}_",
        ),
    )
    return result


def compute_fut_core_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    close = pd.to_numeric(result["close"], errors="coerce")
    low = pd.to_numeric(result["low"], errors="coerce")
    high = pd.to_numeric(result["high"], errors="coerce")

    for label, window, right_offset in FUT_WINDOW_SPECS:
        fut_ma_column = f"fut_ma_{label}"
        result[fut_ma_column] = _centered_rolling_mean(close, window, right_offset)
        result[f"fut_slope_{label}"] = _centered_rolling_slope(close, window, right_offset)
        fut_ma = pd.to_numeric(result[fut_ma_column], errors="coerce")
        result[f"fut_low_dev_{label}"] = _safe_divide(low, fut_ma) - 1.0
        result[f"fut_high_dev_{label}"] = _safe_divide(high, fut_ma) - 1.0
    return result


def compute_fut_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    for left, right in FUT_SPREAD_PAIRS:
        left_ma = pd.to_numeric(result[f"fut_ma_{left}"], errors="coerce")
        right_ma = pd.to_numeric(result[f"fut_ma_{right}"], errors="coerce")
        result[f"fut_spread_{left}_{right}"] = _safe_divide(left_ma, right_ma) - 1.0

    result = _add_drv_columns(
        result,
        FUT_SLOPE_COLUMNS,
        lambda source_column, drv: source_column.replace("fut_slope_", f"fut_slope_drv{drv}_"),
    )
    result = _add_drv_columns(
        result,
        FUT_SPREAD_COLUMNS,
        lambda source_column, drv: source_column.replace("fut_spread_", f"fut_spread_drv{drv}_"),
    )
    result = _add_drv_columns(
        result,
        FUT_LOW_DEV_COLUMNS,
        lambda source_column, drv: source_column.replace("fut_low_dev_", f"fut_low_dev_drv{drv}_"),
    )
    result = _add_drv_columns(
        result,
        FUT_HIGH_DEV_COLUMNS,
        lambda source_column, drv: source_column.replace("fut_high_dev_", f"fut_high_dev_drv{drv}_"),
    )

    for label, window, _ in FUT_WINDOW_SPECS:
        result[f"fut_low_dev_slope_{label}"] = _rolling_slope(result[f"fut_low_dev_{label}"], window)
        result[f"fut_high_dev_slope_{label}"] = _rolling_slope(result[f"fut_high_dev_{label}"], window)

    result = _add_drv_columns(
        result,
        FUT_LOW_DEV_SLOPE_COLUMNS,
        lambda source_column, drv: source_column.replace("fut_low_dev_slope_", f"fut_low_dev_slope_drv{drv}_"),
    )
    result = _add_drv_columns(
        result,
        FUT_HIGH_DEV_SLOPE_COLUMNS,
        lambda source_column, drv: source_column.replace(
            "fut_high_dev_slope_",
            f"fut_high_dev_slope_drv{drv}_",
        ),
    )
    return result


def compute_signed_rolling_percentile(
    series: pd.Series,
    dates: pd.Series,
) -> pd.Series:
    """Compute a signed rolling percentile using a 1-year natural-time window.

    For each row the lookback window covers all preceding rows whose date falls
    within [current_date - 365 days, current_date).  The number of bars in the
    window varies with market calendar; no minimum bar count is enforced.

    Positive values are ranked against the positive sub-history; negative
    values against the absolute negative sub-history (result negated).  A row
    produces NaN when the current value is non-zero but no same-sign value
    exists in the window, or when the current value itself is NaN.
    """
    numeric_series = pd.to_numeric(series, errors="coerce")
    parsed_dates = pd.to_datetime(dates, errors="coerce")
    result = pd.Series(np.nan, index=numeric_series.index, dtype=float)
    window_delta = pd.Timedelta(days=PERCENTILE_CALENDAR_WINDOW)

    for index in range(len(numeric_series)):
        current = numeric_series.iloc[index]
        if pd.isna(current):
            continue
        if current == 0:
            result.iloc[index] = 0.0
            continue
        current_date = parsed_dates.iloc[index]
        if pd.isna(current_date):
            continue
        cutoff_date = current_date - window_delta
        past_values = numeric_series.iloc[:index]
        past_dates = parsed_dates.iloc[:index]
        history = past_values[(past_dates >= cutoff_date) & (past_dates < current_date)]
        if current > 0:
            positive_history = history[history > 0]
            if positive_history.empty:
                continue
            result.iloc[index] = float((positive_history <= current).mean())
            continue
        negative_history_abs = history[history < 0].abs()
        if negative_history_abs.empty:
            continue
        result.iloc[index] = -float((negative_history_abs <= abs(current)).mean())

    return result


def add_percentile_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    dates = result["datetime"]
    percentile_data: dict[str, pd.Series] = {}
    for source_column, percentile_column in FEATURE_VALUE_TO_PERCENTILE_COLUMN.items():
        percentile_data[percentile_column] = compute_signed_rolling_percentile(
            result[source_column],
            dates=dates,
        )
    if percentile_data:
        percentile_df = pd.DataFrame(percentile_data, index=result.index)
        result = pd.concat([result, percentile_df], axis=1)
    return result


def build_trend_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    result = build_hist_reference_columns(df)
    result = compute_hist_ma_features(result)
    result = compute_hist_slope_features(result)
    result = compute_hist_dev_features(result)
    result = compute_hist_derived_features(result)
    result = compute_fut_core_features(result)
    result = compute_fut_derived_features(result)
    result = add_percentile_columns(result)

    for column in OUTPUT_COLUMNS:
        if column not in result.columns:
            result[column] = pd.NA
    return result.loc[:, list(OUTPUT_COLUMNS)].copy()


def order_output_by_midpoint(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    ordered = df.sort_values("datetime", ascending=True).reset_index(drop=True)
    midpoint_index = len(ordered) // 2
    older_block = ordered.iloc[: midpoint_index + 1].iloc[::-1]
    newer_block = ordered.iloc[midpoint_index + 1 :]
    return pd.concat([older_block, newer_block], ignore_index=True)


def clip_to_output_range(
    df: pd.DataFrame,
    *,
    start_date: str | date | datetime,
    end_date: str | date | datetime,
) -> pd.DataFrame:
    start = _coerce_date(start_date)
    end = _coerce_date(end_date)
    dates = pd.to_datetime(df["datetime"], errors="coerce")
    mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    return order_output_by_midpoint(df.loc[mask].reset_index(drop=True))


def save_features_to_csv(df: pd.DataFrame, ticker: str, output_csv_dir: str | Path) -> Path:
    output_dir = Path(output_csv_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{ticker}_trend_features.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def _create_trend_feature_table(connection: sqlite3.Connection, table_name: str) -> None:
    validated_table_name = _validate_identifier(table_name)
    column_sql_parts = [
        f"{column} {COLUMN_TYPE_BY_NAME[column]}"
        for column in OUTPUT_COLUMNS
        if column not in {"ticker", "datetime"}
    ]
    real_column_sql = ",\n            ".join(column_sql_parts)
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {validated_table_name} (
            ticker TEXT NOT NULL,
            datetime TEXT NOT NULL,
            {real_column_sql},
            PRIMARY KEY (ticker, datetime)
        )
        """
    )
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{validated_table_name}_ticker_datetime "
        f"ON {validated_table_name} (ticker, datetime)"
    )


def _ensure_trend_feature_table_columns(connection: sqlite3.Connection, table_name: str) -> None:
    validated_table_name = _validate_identifier(table_name)
    existing_columns = {
        row["name"] for row in connection.execute(f"PRAGMA table_info({validated_table_name})").fetchall()
    }
    for column in OUTPUT_COLUMNS:
        if column in existing_columns:
            continue
        connection.execute(
            f"ALTER TABLE {validated_table_name} ADD COLUMN {column} {COLUMN_TYPE_BY_NAME[column]}"
        )


def init_feature_db(
    feature_db_path: str | Path = DEFAULT_FEATURE_DB_PATH,
    table_name: str = DEFAULT_TABLE_NAME,
) -> None:
    with connect_sqlite(feature_db_path) as connection:
        _create_trend_feature_table(connection, table_name)
        _ensure_trend_feature_table_columns(connection, table_name)


def save_features_to_sqlite(
    df: pd.DataFrame,
    sqlite_path: str | Path,
    table_name: str = DEFAULT_TABLE_NAME,
) -> int:
    if df.empty:
        return 0

    validated_table_name = _validate_identifier(table_name)
    columns = list(OUTPUT_COLUMNS)
    placeholders = ", ".join("?" for _ in columns)
    update_assignments = ", ".join(
        f"{column}=excluded.{column}" for column in columns if column not in {"ticker", "datetime"}
    )
    insert_sql = (
        f"INSERT INTO {validated_table_name} ({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT(ticker, datetime) DO UPDATE SET {update_assignments}"
    )

    records: list[tuple[Any, ...]] = []
    for row in df.loc[:, columns].itertuples(index=False, name=None):
        records.append(tuple(None if pd.isna(value) else value for value in row))

    with connect_sqlite(sqlite_path) as connection:
        _create_trend_feature_table(connection, validated_table_name)
        _ensure_trend_feature_table_columns(connection, validated_table_name)
        connection.executemany(insert_sql, records)
    return len(records)


def compute_trend_features_for_ticker(
    *,
    ticker: str,
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    daily_db_path: str | Path = DEFAULT_DAILY_DB_PATH,
    use_update: bool = False,
) -> pd.DataFrame:
    start = _coerce_date(start_date)
    end = _coerce_date(end_date)
    if end < start:
        raise ValueError("end_date must be greater than or equal to start_date.")

    fetch_start_date = compute_fetch_start_date(start)
    daily_df = load_daily_data_for_feature_research(
        ticker=ticker,
        fetch_start_date=fetch_start_date,
        end_date=end,
        daily_db_path=daily_db_path,
        use_update=use_update,
    )
    feature_df = build_trend_feature_frame(daily_df)
    clipped = clip_to_output_range(feature_df, start_date=start, end_date=end)
    if clipped.empty:
        raise RuntimeError(
            f"No feature rows remained for ticker={ticker} in range=[{start.isoformat()}, {end.isoformat()}]."
        )

    LOGGER.info(
        "feature_compute_done ticker=%s fetch_start=%s raw_rows=%s output_rows=%s",
        ticker,
        fetch_start_date,
        len(daily_df),
        len(clipped),
    )
    return clipped


def run_trend_feature_pipeline(
    *,
    tickers: list[str],
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    daily_db_path: str | Path = DEFAULT_DAILY_DB_PATH,
    feature_db_path: str | Path = DEFAULT_FEATURE_DB_PATH,
    output_csv_dir: str | Path = DEFAULT_OUTPUT_CSV_DIR,
    table_name: str = DEFAULT_TABLE_NAME,
) -> TrendFeatureRunResult:
    if not tickers:
        raise ValueError("tickers must not be empty.")

    success_frames: list[pd.DataFrame] = []
    csv_paths: list[Path] = []
    failed_tickers: list[str] = []

    for ticker in tickers:
        try:
            LOGGER.info("ticker_start ticker=%s", ticker)
            update_feature_db(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                daily_db_path=daily_db_path,
                feature_db_path=feature_db_path,
                table_name=table_name,
            )
            ticker_df = load_feature_rows(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                feature_db_path=feature_db_path,
                table_name=table_name,
            )
            csv_path = save_features_to_csv(ticker_df, ticker=ticker, output_csv_dir=output_csv_dir)
            LOGGER.info("csv_export_done ticker=%s rows=%s path=%s", ticker, len(ticker_df), csv_path)
            success_frames.append(ticker_df)
            csv_paths.append(csv_path)
        except Exception:
            failed_tickers.append(ticker)
            LOGGER.exception("ticker_failed ticker=%s", ticker)

    if not success_frames:
        raise RuntimeError(f"All tickers failed. failed_tickers={failed_tickers}")

    combined_df = pd.concat(success_frames, ignore_index=True)
    LOGGER.info(
        "feature_pipeline_done rows=%s feature_db=%s table=%s failed_tickers=%s",
        len(combined_df),
        feature_db_path,
        table_name,
        failed_tickers,
    )

    return TrendFeatureRunResult(
        combined_df=combined_df,
        csv_paths=csv_paths,
        feature_rows_loaded=len(combined_df),
        failed_tickers=failed_tickers,
    )


def _load_feature_dates(
    *,
    ticker: str,
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    feature_db_path: str | Path = DEFAULT_FEATURE_DB_PATH,
    table_name: str = DEFAULT_TABLE_NAME,
) -> list[str]:
    validated_table_name = _validate_identifier(table_name)
    start = _coerce_date(start_date).isoformat()
    end = _coerce_date(end_date).isoformat()
    with connect_sqlite(feature_db_path) as connection:
        _create_trend_feature_table(connection, validated_table_name)
        _ensure_trend_feature_table_columns(connection, validated_table_name)
        rows = connection.execute(
            f"""
            SELECT datetime
            FROM {validated_table_name}
            WHERE ticker = ? AND datetime >= ? AND datetime <= ?
            ORDER BY datetime ASC
            """,
            (ticker, start, end),
        ).fetchall()
    return [str(row["datetime"]) for row in rows]


def load_feature_rows(
    *,
    ticker: str,
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    feature_db_path: str | Path = DEFAULT_FEATURE_DB_PATH,
    table_name: str = DEFAULT_TABLE_NAME,
) -> pd.DataFrame:
    validated_table_name = _validate_identifier(table_name)
    start = _coerce_date(start_date).isoformat()
    end = _coerce_date(end_date).isoformat()
    with connect_sqlite(feature_db_path) as connection:
        _create_trend_feature_table(connection, validated_table_name)
        _ensure_trend_feature_table_columns(connection, validated_table_name)
        frame = pd.read_sql_query(
            f"""
            SELECT {", ".join(OUTPUT_COLUMNS)}
            FROM {validated_table_name}
            WHERE ticker = ? AND datetime >= ? AND datetime <= ?
            ORDER BY datetime ASC
            """,
            connection,
            params=(ticker, start, end),
        )

    if frame.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    return frame.loc[:, list(OUTPUT_COLUMNS)].copy()


def _find_missing_segments(target_dates: Sequence[str], existing_dates: set[str]) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    start_index: int | None = None

    for index, target_date in enumerate(target_dates):
        if target_date in existing_dates:
            if start_index is not None:
                segments.append((start_index, index - 1))
                start_index = None
            continue
        if start_index is None:
            start_index = index

    if start_index is not None:
        segments.append((start_index, len(target_dates) - 1))
    return segments


def _resolve_actual_warmup_start(
    *,
    daily_df: pd.DataFrame,
    target_start_date: str,
) -> str:
    matches = daily_df.index[daily_df["datetime"] == target_start_date]
    if len(matches) == 0:
        raise RuntimeError(f"Target start date {target_start_date} was not found in daily data.")
    target_index = int(matches[0])
    warmup_index = max(0, target_index - TOTAL_WARMUP_BARS)
    return str(daily_df.iloc[warmup_index]["datetime"])


def _slice_feature_rows_for_dates(feature_df: pd.DataFrame, selected_dates: Sequence[str]) -> pd.DataFrame:
    if not selected_dates:
        return feature_df.iloc[0:0].copy()
    selected_set = set(selected_dates)
    return (
        feature_df.loc[feature_df["datetime"].isin(selected_set)]
        .sort_values("datetime", ascending=True)
        .reset_index(drop=True)
    )


def update_feature_db(
    ticker: str,
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    *,
    daily_db_path: str | Path = DEFAULT_DAILY_DB_PATH,
    feature_db_path: str | Path = DEFAULT_FEATURE_DB_PATH,
    table_name: str = DEFAULT_TABLE_NAME,
) -> bool:
    start = _coerce_date(start_date)
    end = _coerce_date(end_date)
    if end < start:
        raise ValueError("end_date must be greater than or equal to start_date.")

    init_price_db(daily_db_path, "daily_bars")
    init_feature_db(feature_db_path=feature_db_path, table_name=table_name)
    fetch_start_date = compute_fetch_start_date(start)

    update_daily_db(
        ticker=ticker,
        start_date=fetch_start_date,
        end_date=end,
        db_path=daily_db_path,
    )

    future_context_end = end + timedelta(days=FUTURE_CONTEXT_CALENDAR_DAYS)
    full_daily_df = _load_daily_frame(
        ticker=ticker,
        start_date=fetch_start_date,
        end_date=future_context_end,
        daily_db_path=daily_db_path,
    )
    if full_daily_df.empty:
        raise RuntimeError(
            f"No daily bars found for ticker={ticker} in range=[{fetch_start_date}, {future_context_end.isoformat()}]."
        )

    target_daily_df = (
        full_daily_df.loc[
            (full_daily_df["datetime"] >= start.isoformat())
            & (full_daily_df["datetime"] <= end.isoformat())
        ]
        .sort_values("datetime", ascending=True)
        .reset_index(drop=True)
    )
    if target_daily_df.empty:
        raise RuntimeError(
            f"No daily bars found for ticker={ticker} in range=[{start.isoformat()}, {end.isoformat()}]."
        )

    target_dates = target_daily_df["datetime"].tolist()
    full_daily_dates = full_daily_df["datetime"].tolist()
    daily_index_by_date = {value: index for index, value in enumerate(full_daily_dates)}
    existing_feature_dates = set(
        _load_feature_dates(
            ticker=ticker,
            start_date=start,
            end_date=end,
            feature_db_path=feature_db_path,
            table_name=table_name,
        )
    )
    missing_segments = _find_missing_segments(target_dates, existing_feature_dates)
    if not missing_segments:
        return True

    for segment_start_index, segment_end_index in missing_segments:
        segment_start_date = target_dates[segment_start_index]
        segment_end_date = target_dates[segment_end_index]
        segment_start_full_index = daily_index_by_date.get(segment_start_date)
        segment_end_full_index = daily_index_by_date.get(segment_end_date)
        if segment_start_full_index is None or segment_end_full_index is None:
            raise RuntimeError(
                f"Could not align daily rows for ticker={ticker} segment=[{segment_start_date}, {segment_end_date}]."
            )

        recalc_start_index = max(0, segment_start_full_index - FUTURE_BACKFILL_BARS)
        compute_end_index = min(len(full_daily_dates) - 1, segment_end_full_index + FUTURE_BACKFILL_BARS)
        recalc_start_date = full_daily_dates[recalc_start_index]
        compute_end_date = full_daily_dates[compute_end_index]
        left_backfill_dates = full_daily_dates[recalc_start_index:segment_start_full_index]
        missing_dates = target_dates[segment_start_index : segment_end_index + 1]
        existing_left_feature_dates = set(
            _load_feature_dates(
                ticker=ticker,
                start_date=recalc_start_date,
                end_date=segment_start_date,
                feature_db_path=feature_db_path,
                table_name=table_name,
            )
        )
        persist_dates = [
            *[target_date for target_date in left_backfill_dates if target_date in existing_left_feature_dates],
            *missing_dates,
        ]

        warmup_start_date = _resolve_actual_warmup_start(
            daily_df=full_daily_df,
            target_start_date=recalc_start_date,
        )
        compute_daily_df = (
            full_daily_df.loc[
                (full_daily_df["datetime"] >= warmup_start_date)
                & (full_daily_df["datetime"] <= compute_end_date)
            ]
            .sort_values("datetime", ascending=True)
            .reset_index(drop=True)
        )

        feature_df = build_trend_feature_frame(compute_daily_df)
        segment_feature_df = _slice_feature_rows_for_dates(feature_df, persist_dates)
        save_features_to_sqlite(segment_feature_df, sqlite_path=feature_db_path, table_name=table_name)

    return True


# ---------------------------------------------------------------------------
# Minimal MA features for the backtest engine
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class MAFeatures:
    """Lightweight MA snapshot computed directly from a close-price sequence."""

    ticker: str
    trade_date: date
    ma5: float
    ma20: float
    ma60: float
    close: float


def compute_ma_features(
    *,
    ticker: str,
    trade_date: date,
    closes: list[float],
) -> MAFeatures:
    """Compute simple moving averages from a growing list of close prices.

    Called once per bar inside the backtest loop; requires at least 60 values
    (the engine enforces MIN_TREND_BARS = 63 before the first call).
    """
    n = len(closes)
    close = closes[-1]
    ma5 = sum(closes[max(0, n - 5) :]) / min(n, 5)
    ma20 = sum(closes[max(0, n - 20) :]) / min(n, 20)
    ma60 = sum(closes[max(0, n - 60) :]) / min(n, 60)
    return MAFeatures(ticker=ticker, trade_date=trade_date, ma5=ma5, ma20=ma20, ma60=ma60, close=close)


__all__ = [
    "DEFAULT_DAILY_DB_PATH",
    "DEFAULT_FEATURE_DB_PATH",
    "DEFAULT_OUTPUT_CSV_DIR",
    "DEFAULT_TABLE_NAME",
    "MAFeatures",
    "OUTPUT_COLUMNS",
    "PERCENTILE_CALENDAR_WINDOW",
    "TrendFeatureRunResult",
    "_compute_linear_slope",
    "add_percentile_columns",
    "build_trend_feature_frame",
    "clip_to_output_range",
    "compute_fetch_start_date",
    "compute_hist_warmup_bars",
    "compute_ma_features",
    "compute_signed_rolling_percentile",
    "compute_trend_features_for_ticker",
    "init_feature_db",
    "load_daily_data_for_feature_research",
    "load_feature_rows",
    "order_output_by_midpoint",
    "run_trend_feature_pipeline",
    "save_features_to_csv",
    "save_features_to_sqlite",
    "update_feature_db",
]

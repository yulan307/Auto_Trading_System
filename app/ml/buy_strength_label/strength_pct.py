from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from app.ml.buy_strength_label.repository import load_strength_rows
from app.ml.buy_strength_label.updater import update_buy_strength_db
from app.ml.common.paths import DEFAULT_BUY_STRENGTH_DB_PATH, DEFAULT_FEATURE_DB_PATH
from app.ml.common.utils import coerce_date_str, normalize_tickers, subtract_months, subtract_years


LOGGER = logging.getLogger(__name__)


def _compute_strength_pct_for_ticker(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values("date", ascending=True).reset_index(drop=True).copy()
    ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce")
    strength_pct_values: list[float] = []

    for row in ordered.itertuples(index=False):
        current_date = pd.Timestamp(row.date)
        window_start = current_date - pd.DateOffset(years=2)
        history = ordered.loc[
            (ordered["date"] >= window_start) & (ordered["date"] <= current_date),
            "strength",
        ].astype(float)
        if history.empty:
            strength_pct_values.append(float("nan"))
            continue
        strength_pct_values.append(float((history <= float(row.strength)).mean()))

    ordered["date"] = ordered["date"].dt.strftime("%Y-%m-%d")
    ordered["strength_pct"] = np.asarray(strength_pct_values, dtype=float)
    return ordered


def get_strength_pct_frame(
    tickers,
    end_date: str | None = None,
    strength_pct_length_month: int = 24,
    feature_db_path: str = str(DEFAULT_FEATURE_DB_PATH),
    strength_db_path: str = str(DEFAULT_BUY_STRENGTH_DB_PATH),
) -> pd.DataFrame:
    if strength_pct_length_month <= 0:
        raise ValueError("strength_pct_length_month must be greater than 0.")

    normalized_tickers = normalize_tickers(tickers)
    end = coerce_date_str(end_date, default_today=True)
    output_start = subtract_months(end, strength_pct_length_month)
    read_start = subtract_years(output_start, 2)

    result_frames: list[pd.DataFrame] = []
    for ticker in normalized_tickers:
        update_buy_strength_db(
            ticker=ticker,
            start_date=read_start,
            end_date=end,
            feature_db_path=feature_db_path,
            strength_db_path=strength_db_path,
        )
        strength_df = load_strength_rows(
            tickers=ticker,
            start_date=read_start,
            end_date=end,
            db_path=strength_db_path,
        )
        if strength_df.empty:
            continue

        ticker_result = _compute_strength_pct_for_ticker(strength_df)
        ticker_result = ticker_result.loc[
            (ticker_result["date"] >= output_start) & (ticker_result["date"] <= end),
            ["ticker", "date", "strength", "label_version", "strength_pct"],
        ].reset_index(drop=True)
        result_frames.append(ticker_result)

    if not result_frames:
        return pd.DataFrame(columns=["ticker", "date", "strength", "label_version", "strength_pct"])

    combined = pd.concat(result_frames, ignore_index=True)
    LOGGER.info(
        "strength_pct_frame_ready tickers=%s start=%s end=%s rows=%s",
        normalized_tickers,
        output_start,
        end,
        len(combined),
    )
    return combined

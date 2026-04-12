from __future__ import annotations

import logging

import pandas as pd

from app.ml.buy_strength_label.generator import compute_raw_strength_from_feature_df
from app.ml.buy_strength_label.init_db import init_buy_strength_db
from app.ml.buy_strength_label.repository import get_existing_strength_dates, upsert_strength_rows
from app.ml.common.paths import DEFAULT_BUY_STRENGTH_DB_PATH, DEFAULT_FEATURE_DB_PATH
from app.ml.common.utils import coerce_date_str
from app.trend.features import load_feature_rows, update_feature_db


LOGGER = logging.getLogger(__name__)


def update_buy_strength_db(
    ticker: str,
    start_date: str,
    end_date: str,
    feature_db_path: str = str(DEFAULT_FEATURE_DB_PATH),
    strength_db_path: str = str(DEFAULT_BUY_STRENGTH_DB_PATH),
) -> dict:
    normalized_ticker = str(ticker).strip().upper()
    start = coerce_date_str(start_date)
    end = coerce_date_str(end_date)
    if end < start:
        raise ValueError("end_date must be greater than or equal to start_date.")

    init_buy_strength_db(db_path=strength_db_path)
    existing_dates = get_existing_strength_dates(
        ticker=normalized_ticker,
        start_date=start,
        end_date=end,
        db_path=strength_db_path,
    )

    update_feature_db(
        ticker=normalized_ticker,
        start_date=start,
        end_date=end,
        feature_db_path=feature_db_path,
    )
    feature_df = load_feature_rows(
        ticker=normalized_ticker,
        start_date=start,
        end_date=end,
        feature_db_path=feature_db_path,
    )
    if feature_df.empty:
        return {
            "ticker": normalized_ticker,
            "start_date": start,
            "end_date": end,
            "existing_rows": len(existing_dates),
            "new_rows": 0,
            "skipped_rows": 0,
            "status": "ok",
        }

    feature_df = feature_df.rename(columns={"datetime": "date"}).copy()
    missing_feature_df = feature_df.loc[~feature_df["date"].astype(str).isin(existing_dates)].copy()
    if missing_feature_df.empty:
        return {
            "ticker": normalized_ticker,
            "start_date": start,
            "end_date": end,
            "existing_rows": len(existing_dates),
            "new_rows": 0,
            "skipped_rows": 0,
            "status": "ok",
        }

    missing_feature_df = missing_feature_df.rename(columns={"date": "datetime"})
    generated_df = compute_raw_strength_from_feature_df(missing_feature_df)
    new_rows = upsert_strength_rows(generated_df, db_path=strength_db_path)
    skipped_rows = max(len(missing_feature_df) - len(generated_df), 0)

    LOGGER.info(
        "buy_strength_update_done ticker=%s start=%s end=%s existing_rows=%s new_rows=%s skipped_rows=%s",
        normalized_ticker,
        start,
        end,
        len(existing_dates),
        new_rows,
        skipped_rows,
    )
    return {
        "ticker": normalized_ticker,
        "start_date": start,
        "end_date": end,
        "existing_rows": len(existing_dates),
        "new_rows": new_rows,
        "skipped_rows": skipped_rows,
        "status": "ok",
    }

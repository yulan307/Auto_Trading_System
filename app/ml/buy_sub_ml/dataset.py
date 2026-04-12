from __future__ import annotations

import logging

import pandas as pd

from app.ml.buy_strength_label.strength_pct import get_strength_pct_frame
from app.ml.buy_sub_ml.feature_selector import select_hist_feature_columns
from app.ml.common.paths import DEFAULT_BUY_STRENGTH_DB_PATH, DEFAULT_FEATURE_DB_PATH
from app.ml.common.utils import normalize_tickers
from app.trend.features import load_feature_rows, update_feature_db


LOGGER = logging.getLogger(__name__)


def build_buy_sub_ml_dataset(
    tickers,
    end_date: str | None,
    strength_pct_length_month: int,
    feature_db_path: str = str(DEFAULT_FEATURE_DB_PATH),
    strength_db_path: str = str(DEFAULT_BUY_STRENGTH_DB_PATH),
):
    normalized_tickers = normalize_tickers(tickers)
    label_df = get_strength_pct_frame(
        tickers=normalized_tickers,
        end_date=end_date,
        strength_pct_length_month=strength_pct_length_month,
        feature_db_path=feature_db_path,
        strength_db_path=strength_db_path,
    )
    if label_df.empty:
        return pd.DataFrame(columns=["ticker", "date", "strength_pct"])

    start_date = str(label_df["date"].min())
    final_end_date = str(label_df["date"].max())
    feature_frames: list[pd.DataFrame] = []
    for ticker in normalized_tickers:
        update_feature_db(
            ticker=ticker,
            start_date=start_date,
            end_date=final_end_date,
            feature_db_path=feature_db_path,
        )
        ticker_features = load_feature_rows(
            ticker=ticker,
            start_date=start_date,
            end_date=final_end_date,
            feature_db_path=feature_db_path,
        )
        if ticker_features.empty:
            continue
        ticker_features = ticker_features.rename(columns={"datetime": "date"})
        hist_columns = [column for column in ticker_features.columns if column.startswith("hist_")]
        feature_frames.append(ticker_features.loc[:, ["ticker", "date", *hist_columns]].copy())

    if not feature_frames:
        return pd.DataFrame(columns=["ticker", "date", "strength_pct"])

    feature_df = pd.concat(feature_frames, ignore_index=True)
    merged = label_df.merge(feature_df, on=["ticker", "date"], how="left")
    feature_columns = select_hist_feature_columns(merged)
    dataset = merged.loc[:, ["ticker", "date", *feature_columns, "strength_pct"]].copy()
    dataset = dataset.dropna(subset=[*feature_columns, "strength_pct"]).reset_index(drop=True)

    LOGGER.info(
        "buy_sub_ml_dataset_ready tickers=%s rows=%s features=%s",
        normalized_tickers,
        len(dataset),
        len(feature_columns),
    )
    return dataset

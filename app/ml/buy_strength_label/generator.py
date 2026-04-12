from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.ml.common.schemas import BUY_STRENGTH_LABEL_VERSION


REQUIRED_FEATURE_COLUMNS = ("ticker", "datetime", "fut_low_dev_w", "fut_low_dev_m", "fut_low_dev_drv2_w")


def compute_raw_strength_from_feature_df(feature_df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_FEATURE_COLUMNS if column not in feature_df.columns]
    if missing:
        raise ValueError(f"Feature frame missing required columns: {missing}")

    frame = feature_df.loc[:, list(REQUIRED_FEATURE_COLUMNS)].copy()
    frame["fut_low_dev_w"] = pd.to_numeric(frame["fut_low_dev_w"], errors="coerce")
    frame["fut_low_dev_m"] = pd.to_numeric(frame["fut_low_dev_m"], errors="coerce")
    frame["fut_low_dev_drv2_w"] = pd.to_numeric(frame["fut_low_dev_drv2_w"], errors="coerce")
    frame = frame.dropna(subset=["ticker", "datetime", "fut_low_dev_w", "fut_low_dev_m", "fut_low_dev_drv2_w"]).copy()

    score = np.maximum.reduce(
        [
            -frame["fut_low_dev_w"].to_numpy(dtype=float),
            -frame["fut_low_dev_m"].to_numpy(dtype=float),
            np.zeros(len(frame), dtype=float),
        ]
    )
    strength = np.maximum(score * frame["fut_low_dev_drv2_w"].to_numpy(dtype=float), 0.0)

    result = pd.DataFrame(
        {
            "ticker": frame["ticker"].astype(str).str.upper(),
            "date": pd.to_datetime(frame["datetime"], errors="coerce").dt.strftime("%Y-%m-%d"),
            "strength": strength.astype(float),
            "label_version": BUY_STRENGTH_LABEL_VERSION,
            "update_time": datetime.now(timezone.utc).isoformat(),
        }
    )
    result = result.dropna(subset=["date"]).drop_duplicates(subset=["ticker", "date"], keep="last")
    return result.reset_index(drop=True)

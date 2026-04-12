from __future__ import annotations

import pandas as pd


LEAKY_PREFIXES = ("fut_",)
LEAKY_COLUMNS = {"ticker", "date", "strength", "strength_pct", "score", "raw_strength", "label_version"}


def select_hist_feature_columns(df: pd.DataFrame) -> list[str]:
    selected: list[str] = []
    for column in df.columns:
        if column in LEAKY_COLUMNS or any(column.startswith(prefix) for prefix in LEAKY_PREFIXES):
            continue
        if not column.startswith("hist_"):
            continue
        if not pd.api.types.is_numeric_dtype(df[column]):
            continue
        selected.append(column)
    if not selected:
        raise ValueError("No valid hist_* numeric feature columns were found.")
    return selected

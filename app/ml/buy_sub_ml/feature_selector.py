from __future__ import annotations

import pandas as pd


LEAKY_PREFIXES = ("fut_",)
LEAKY_COLUMNS = {
    "ticker",
    "date",
    "datetime",
    "strength",
    "strength_pct",
    "score",
    "raw_strength",
    "label_version",
    "regime",
}


def select_hist_feature_columns(df: pd.DataFrame) -> list[str]:
    selected = sorted(
        column
        for column in df.columns
        if column.startswith("hist_")
        and column not in LEAKY_COLUMNS
        and not any(column.startswith(prefix) for prefix in LEAKY_PREFIXES)
        and pd.api.types.is_numeric_dtype(df[column])
    )
    if not selected:
        raise ValueError("No valid hist_* numeric feature columns were found.")
    return selected

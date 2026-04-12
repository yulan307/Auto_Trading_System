from __future__ import annotations

from app.ml.buy_strength_label.db import ensure_buy_strength_table
from app.ml.common.paths import DEFAULT_BUY_STRENGTH_DB_PATH
from app.ml.common.schemas import BUY_STRENGTH_TABLE_NAME


def init_buy_strength_db(
    db_path: str = str(DEFAULT_BUY_STRENGTH_DB_PATH),
    table_name: str = BUY_STRENGTH_TABLE_NAME,
) -> None:
    ensure_buy_strength_table(db_path=db_path, table_name=table_name)

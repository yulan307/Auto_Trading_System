from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.data.db import connect_sqlite, init_logs_db


@dataclass(slots=True)
class LogEvent:
    event_time: datetime
    level: str
    module: str
    event_type: str
    ticker: str | None
    message: str
    payload_json: str | None


def init_event_store(db_path: str | Path) -> None:
    init_logs_db(db_path)


def insert_log_event(
    db_path: str | Path,
    *,
    event_time: datetime,
    level: str,
    module: str,
    event_type: str,
    ticker: str | None,
    message: str,
    payload: dict | None,
) -> None:
    init_event_store(db_path)
    payload_json = json.dumps(payload, ensure_ascii=True, sort_keys=True) if payload is not None else None
    with connect_sqlite(db_path) as connection:
        connection.execute(
            """
            INSERT INTO log_events (
                event_time, level, module, event_type, ticker, message, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_time.isoformat(),
                level,
                module,
                event_type,
                ticker,
                message,
                payload_json,
            ),
        )

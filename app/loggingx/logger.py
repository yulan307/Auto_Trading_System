from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.loggingx.event_store import insert_log_event


EVENT_TYPES_FOR_TRADE_LOG = {"order_submit", "order_cancel", "order_fill", "account_update"}
EVENT_TYPES_FOR_DECISION_LOG = {"daily_signal", "intraday_track"}


class EventTypeFilter(logging.Filter):
    def __init__(self, *, allowed_event_types: set[str] | None = None, min_level: int | None = None) -> None:
        super().__init__()
        self.allowed_event_types = allowed_event_types
        self.min_level = min_level

    def filter(self, record: logging.LogRecord) -> bool:
        if self.min_level is not None and record.levelno < self.min_level:
            return False
        if self.allowed_event_types is None:
            return True
        return getattr(record, "event_type", None) in self.allowed_event_types


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload_json = getattr(record, "payload_json", "")
        ticker = getattr(record, "ticker", "") or ""
        module_name = getattr(record, "module_name", record.name)
        event_type = getattr(record, "event_type", "event")
        timestamp = self.formatTime(record, self.datefmt)
        return f"{timestamp} | {record.levelname} | {module_name} | {event_type} | {ticker} | {record.getMessage()} | {payload_json}"


@dataclass(slots=True)
class AppLogger:
    _logger: logging.Logger
    logs_db_path: str

    def log_event(
        self,
        *,
        level: str,
        module: str,
        event_type: str,
        message: str,
        ticker: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        level_name = level.upper()
        if level_name not in logging.getLevelNamesMapping():
            raise ValueError(f"Unsupported log level: {level}")

        payload_json = json.dumps(payload, ensure_ascii=True, sort_keys=True) if payload is not None else ""
        event_time = datetime.utcnow()
        self._logger.log(
            logging.getLevelNamesMapping()[level_name],
            message,
            extra={
                "module_name": module,
                "event_type": event_type,
                "ticker": ticker,
                "payload_json": payload_json,
            },
        )
        insert_log_event(
            self.logs_db_path,
            event_time=event_time,
            level=level_name,
            module=module,
            event_type=event_type,
            ticker=ticker,
            message=message,
            payload=payload,
        )

    def shutdown(self) -> None:
        for handler in list(self._logger.handlers):
            handler.flush()
            handler.close()
            self._logger.removeHandler(handler)


def _build_file_handler(path: Path, *, level: int, filter_obj: logging.Filter | None = None) -> logging.Handler:
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(level)
    if filter_obj is not None:
        handler.addFilter(filter_obj)
    handler.setFormatter(StructuredFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
    return handler


def setup_logging(config: dict[str, Any]) -> AppLogger:
    log_dir = Path(config["logging"]["log_dir"]).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    logs_db_path = config["data"]["logs_db_path"]
    level_name = config["logging"]["log_level"].upper()
    if level_name not in logging.getLevelNamesMapping():
        raise ValueError(f"Unsupported log level: {level_name}")

    logger_name = f"trading_system.{log_dir}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.getLevelNamesMapping()[level_name])
    logger.propagate = False

    if logger.handlers:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.getLevelNamesMapping()[level_name])
    console_handler.setFormatter(StructuredFormatter(datefmt="%Y-%m-%d %H:%M:%S"))

    app_handler = _build_file_handler(log_dir / "app.log", level=logging.getLevelNamesMapping()[level_name])
    trade_handler = _build_file_handler(
        log_dir / "trade.log",
        level=logging.INFO,
        filter_obj=EventTypeFilter(allowed_event_types=EVENT_TYPES_FOR_TRADE_LOG),
    )
    decision_handler = _build_file_handler(
        log_dir / "decision.log",
        level=logging.INFO,
        filter_obj=EventTypeFilter(allowed_event_types=EVENT_TYPES_FOR_DECISION_LOG),
    )
    error_handler = _build_file_handler(
        log_dir / "error.log",
        level=logging.ERROR,
        filter_obj=EventTypeFilter(min_level=logging.ERROR),
    )

    for handler in (console_handler, app_handler, trade_handler, decision_handler, error_handler):
        logger.addHandler(handler)

    return AppLogger(_logger=logger, logs_db_path=logs_db_path)

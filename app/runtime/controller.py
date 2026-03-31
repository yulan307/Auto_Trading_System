from __future__ import annotations

from app.loggingx.logger import setup_logging
from app.runtime.config_loader import load_config
from app.runtime.context import RuntimeContext


def init_runtime(config_path: str) -> dict:
    config = load_config(config_path)
    logger = setup_logging(config)
    runtime_context = RuntimeContext(
        mode=config["mode"],
        config=config,
        logger=logger,
        metadata={"config_path": str(config_path)},
    )
    logger.log_event(
        level="INFO",
        module="runtime.controller",
        event_type="system_init",
        message="Runtime context initialized.",
        payload={"mode": config["mode"]},
    )
    return runtime_context.to_dict()

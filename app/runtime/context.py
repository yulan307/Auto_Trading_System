from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RuntimeContext:
    mode: str
    config: dict[str, Any]
    logger: Any
    daily_provider: Any | None = None
    intraday_provider: Any | None = None
    symbol_manager: Any | None = None
    account_manager: Any | None = None
    execution_engine: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "config": self.config,
            "logger": self.logger,
            "daily_provider": self.daily_provider,
            "intraday_provider": self.intraday_provider,
            "symbol_manager": self.symbol_manager,
            "account_manager": self.account_manager,
            "execution_engine": self.execution_engine,
            "metadata": self.metadata,
        }

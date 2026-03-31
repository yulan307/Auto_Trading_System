from __future__ import annotations

from app.symbols.models import SymbolInfo
from app.symbols.repository import SymbolRepository


class SymbolManager:
    def __init__(self, repository: SymbolRepository) -> None:
        self.repository = repository

    def add_symbol(self, symbol_info: SymbolInfo):
        self.repository.add_symbol(symbol_info)

    def get_symbol(self, symbol: str):
        return self.repository.get_symbol(symbol)

    def update_symbol(self, symbol: str, updates: dict):
        self.repository.update_symbol(symbol, updates)

    def list_enabled_symbols(self, mode: str):
        mode_key_map = {
            "backtest": "enabled_for_backtest",
            "paper": "enabled_for_paper",
            "live": "enabled_for_live",
        }
        if mode not in mode_key_map:
            raise ValueError(f"Unsupported mode: {mode}")
        key = mode_key_map[mode]

        # 简化实现：按常见场景（少量标的）扫描并过滤。
        enabled: list[SymbolInfo] = []
        from app.data.db import connect_sqlite

        with connect_sqlite(self.repository.db_path) as connection:
            rows = connection.execute("SELECT symbol FROM symbols").fetchall()
            for row in rows:
                item = self.repository.get_symbol(row["symbol"])
                if item and getattr(item, key):
                    enabled.append(item)
        return enabled

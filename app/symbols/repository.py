from __future__ import annotations


class SymbolRepository:
    def add_symbol(self, symbol_info):
        raise NotImplementedError("SymbolRepository will be implemented in phase 3.")

    def get_symbol(self, symbol: str):
        raise NotImplementedError("SymbolRepository will be implemented in phase 3.")

    def update_symbol(self, symbol: str, updates: dict):
        raise NotImplementedError("SymbolRepository will be implemented in phase 3.")

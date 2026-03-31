from __future__ import annotations


class SymbolManager:
    def add_symbol(self, symbol_info):
        raise NotImplementedError("SymbolManager will be implemented in phase 3.")

    def get_symbol(self, symbol: str):
        raise NotImplementedError("SymbolManager will be implemented in phase 3.")

    def update_symbol(self, symbol: str, updates: dict):
        raise NotImplementedError("SymbolManager will be implemented in phase 3.")

    def list_enabled_symbols(self, mode: str):
        raise NotImplementedError("SymbolManager will be implemented in phase 3.")

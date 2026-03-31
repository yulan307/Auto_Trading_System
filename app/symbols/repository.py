from __future__ import annotations

import json
from dataclasses import asdict

from app.data.db import connect_sqlite
from app.symbols.models import SymbolInfo


class SymbolRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def add_symbol(self, symbol_info: SymbolInfo) -> None:
        data = asdict(symbol_info)
        with connect_sqlite(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO symbols (
                    symbol, market, asset_type, currency, timezone,
                    enabled_for_backtest, enabled_for_live, enabled_for_paper,
                    tags, data_provider, broker_route, strategy_profile,
                    base_trade_amount_usd, max_position_usd, weekly_budget_multiplier,
                    allow_force_buy_last_bar, allow_fractional
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["symbol"],
                    data["market"],
                    data["asset_type"],
                    data["currency"],
                    data["timezone"],
                    int(data["enabled_for_backtest"]),
                    int(data["enabled_for_live"]),
                    int(data["enabled_for_paper"]),
                    json.dumps(data["tags"], ensure_ascii=False),
                    data["data_provider"],
                    data["broker_route"],
                    data["strategy_profile"],
                    data["base_trade_amount_usd"],
                    data["max_position_usd"],
                    data["weekly_budget_multiplier"],
                    int(data["allow_force_buy_last_bar"]),
                    int(data["allow_fractional"]),
                ),
            )

    def get_symbol(self, symbol: str) -> SymbolInfo | None:
        with connect_sqlite(self.db_path) as connection:
            row = connection.execute("SELECT * FROM symbols WHERE symbol = ?", (symbol,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["tags"] = json.loads(data["tags"] or "[]")
        for key in (
            "enabled_for_backtest",
            "enabled_for_live",
            "enabled_for_paper",
            "allow_force_buy_last_bar",
            "allow_fractional",
        ):
            data[key] = bool(data[key])
        return SymbolInfo(**data)

    def update_symbol(self, symbol: str, updates: dict) -> None:
        if not updates:
            return
        converted = dict(updates)
        if "tags" in converted:
            converted["tags"] = json.dumps(converted["tags"], ensure_ascii=False)
        bool_keys = {
            "enabled_for_backtest",
            "enabled_for_live",
            "enabled_for_paper",
            "allow_force_buy_last_bar",
            "allow_fractional",
        }
        for key in bool_keys & converted.keys():
            converted[key] = int(bool(converted[key]))

        set_clause = ", ".join(f"{k} = ?" for k in converted)
        params = list(converted.values()) + [symbol]
        with connect_sqlite(self.db_path) as connection:
            connection.execute(f"UPDATE symbols SET {set_clause} WHERE symbol = ?", params)

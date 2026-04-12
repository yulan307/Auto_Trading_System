from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "backtest",
    "timezone": "America/New_York",
    "data": {
        "daily_provider": "local",
        "intraday_provider": "local",
        "daily_db_path": "data/daily.db",
        "feature_db_path": "data/feature.db",
        "intraday_db_path": "data/intraday.db",
        "symbols_db_path": "data/symbols.db",
        "account_db_path": "data/account.db",
        "logs_db_path": "data/logs.db",
    },
    "account": {
        "account_source": "local_virtual",
        "initial_cash": 100000,
    },
    "execution": {
        "broker": "mock",
        "allow_fractional_default": False,
    },
    "logging": {
        "log_level": "INFO",
        "log_dir": "logs",
    },
    "strategy": {
        "ma_windows": [5, 20, 60],
        "intraday_interval": "15m",
        "last_bar_force_trade": True,
    },
    "ml": {
        "enabled": True,
        "buy_model_version": "buy/v001",
        "sell_model_version": None,
    },
}

VALID_MODES = {"backtest", "paper", "live"}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
            continue
        merged[key] = value
    return merged


def _project_root_from_config(config_path: Path) -> Path:
    if config_path.parent.name == "config":
        return config_path.parent.parent.resolve()
    return config_path.parent.resolve()


def _resolve_runtime_paths(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    resolved = deepcopy(config)
    path_keys = {
        "daily_db_path",
        "feature_db_path",
        "intraday_db_path",
        "symbols_db_path",
        "account_db_path",
        "logs_db_path",
        "log_dir",
    }

    for _, section in resolved.items():
        if not isinstance(section, dict):
            continue
        for key, value in section.items():
            if key not in path_keys or not isinstance(value, str):
                continue
            section[key] = str((project_root / value).resolve())

    resolved["project_root"] = str(project_root)
    return resolved


def _validate_config(config: dict[str, Any]) -> None:
    mode = config.get("mode")
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported mode: {mode!r}. Expected one of {sorted(VALID_MODES)}.")

    missing_sections = [
        section
        for section in ("data", "account", "execution", "logging", "strategy", "ml")
        if section not in config
    ]
    if missing_sections:
        raise ValueError(f"Missing required config sections: {', '.join(missing_sections)}.")


def load_config(config_path: str | Path) -> dict[str, Any]:
    config_file = Path(config_path).resolve()
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a YAML mapping at the root level.")

    merged = _deep_merge(DEFAULT_CONFIG, raw)
    project_root = _project_root_from_config(config_file)
    resolved = _resolve_runtime_paths(merged, project_root)
    _validate_config(resolved)
    return resolved

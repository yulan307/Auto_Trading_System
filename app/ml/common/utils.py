from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd


def normalize_tickers(tickers: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(tickers, str):
        normalized = [tickers.strip().upper()]
    else:
        normalized = [str(ticker).strip().upper() for ticker in tickers]
    normalized = [ticker for ticker in normalized if ticker]
    if not normalized:
        raise ValueError("tickers must not be empty.")
    return normalized


def coerce_date_str(value: str | date | datetime | None, default_today: bool = False) -> str:
    if value is None:
        if not default_today:
            raise ValueError("date value must not be None.")
        return date.today().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return pd.Timestamp(str(value)).date().isoformat()


def subtract_months(value: str | date | datetime, months: int) -> str:
    if months < 0:
        raise ValueError("months must be greater than or equal to 0.")
    return (pd.Timestamp(coerce_date_str(value)) - pd.DateOffset(months=months)).date().isoformat()


def subtract_years(value: str | date | datetime, years: int) -> str:
    if years < 0:
        raise ValueError("years must be greater than or equal to 0.")
    return (pd.Timestamp(coerce_date_str(value)) - pd.DateOffset(years=years)).date().isoformat()


def ensure_directory(path: str | Path) -> Path:
    target = Path(path).resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def normalize_buy_model_version(model_version: str) -> tuple[str, str]:
    cleaned = str(model_version).strip().replace("\\", "/")
    if not cleaned:
        raise ValueError("model_version must not be empty.")
    if cleaned.startswith("buy/"):
        version_name = cleaned.split("/", 1)[1]
        registry_value = cleaned
    elif "/" not in cleaned:
        version_name = cleaned
        registry_value = f"buy/{cleaned}"
    else:
        version_name = cleaned.split("/")[-1]
        registry_value = cleaned
    return registry_value, version_name


def format_model_version_for_filename(model_version: str) -> str:
    registry_value, _ = normalize_buy_model_version(model_version)
    return registry_value.replace("/", "_")


def end_of_day_iso(value: str | date | datetime | None = None) -> str:
    return coerce_date_str(value, default_today=True)


def validate_sqlite_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise ValueError(f"Invalid SQLite identifier: {identifier!r}")
    return identifier

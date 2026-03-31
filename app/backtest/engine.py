from __future__ import annotations


def run_backtest(*, ticker: str, start_date, end_date, runtime_context) -> dict:
    return {
        "ticker": ticker,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "mode": runtime_context.get("mode", "backtest"),
        "status": "initialized",
        "trades": [],
        "decisions": [],
        "metrics": {},
    }

from __future__ import annotations

import argparse
import json

from app.runtime.controller import init_runtime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize trading system runtime.")
    parser.add_argument(
        "--config",
        default="config/backtest.yaml",
        help="Path to the YAML config file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime = init_runtime(args.config)
    runtime["logger"].log_event(
        level="INFO",
        module="main",
        event_type="system_init",
        message="Runtime initialized.",
        payload={"mode": runtime["mode"]},
    )
    summary = {
        "mode": runtime["mode"],
        "project_root": runtime["config"]["project_root"],
        "log_dir": runtime["config"]["logging"]["log_dir"],
    }
    print(json.dumps(summary, indent=2))
    runtime["logger"].shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

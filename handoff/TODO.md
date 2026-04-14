# TODO

## Now

- [ ] 新开分支 `feature/ml-signal-integration`，实现 ML 信号接入（见 CURRENT.md 完整设计）
- [ ] 合并后重新填充 `feature.db`（`compute_trend_features` for all local tickers）

## Next

- 多标的回测循环（当前 `run_backtest` 只支持单 ticker）
- 手续费模型（当前固定为 0）
- 回测报告模块（`app/backtest/report.py` 目前是 stub）

## Later

- 接入 15 分钟日内回放代替日线 high/low 触发
- Paper trading 模式数据源接入
- README / docs 与实际实现保持同步

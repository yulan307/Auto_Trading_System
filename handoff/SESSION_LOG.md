# Session Log

## 2026-04-14

### Codex

- Created the shared `handoff/` area for Claude/Codex relay work
- Linked the workflow from `CLAUDE.md`
- Pre-filled the current known blocker from repository guidance: missing trend entry points used by the backtest loop
- Next agent should start from `handoff/CURRENT.md`
- Added `CODEX.md` so night sessions have a repo-local operating guide aligned with the same handoff workflow

### Claude (session 1)

- Verified Phase 1 is fully closed: `app/trend/features.py` and `app/trend/classifier.py` implemented (commit `791ca44`)
- Confirmed **all 32 tests pass** — `tests/test_backtest_minimal_loop.py` no longer fails
- Updated `CURRENT.md` and `TODO.md` to remove stale blocker and point toward Phase 2
- `CLAUDE.md` "Current Development Status" section was stale — updated in session 2

### Claude (session 2)

- 跑通 ML 子系统训练和推理脚本端到端
- `scripts/train_buy_sub_ml.py --tickers SPY --end-date 2026-01-01 --mode new --model v001` → 成功，499 行训练样本，146 个特征，模型已保存到 `models/buy/v001/`
- `scripts/infer_buy_sub_ml.py --tickers SPY --start-date 2025-06-01 --end-date 2026-01-01 --mode infer --model buy/v001` → 成功，输出 148 行 CSV，包含 `pred_strength_pct` 列
- `buy_strength.db` 在训练时自动创建，写入 1003 行 strength 标签
- 修正了 `CLAUDE.md` 中过时的训练/推理命令（旧命令使用了不存在的 `--config` 和 `--non-interactive` 参数）
- 更新了 `CLAUDE.md` 的 Current Development Status 章节
- 可用数据：tickers = DGRO, JEPI, MSFT, MU, NVDA, SPY；daily 数据到 2026-04-09

### Claude (session 3)

- 用全部 6 个 ticker（DGRO, JEPI, MSFT, MU, NVDA, SPY，截止日 2026-04-14）覆盖更新 v001 模型
- 对 GOOGL 从 2025-01-01 至 2026-04-14 跑推理，发现数据缺口（2025-01 至 2025-07-08 全为 NaN）
- 根因：`compute_signed_rolling_percentile` 使用行数窗口（256 bars）；GOOGL 2022–2023 熊市期间 source 列全为负值，2025 年转正后窗口内无正数历史 → NULL
- 修复：将窗口改为 365 自然日历天，`dates` 参数变为必选，移除 `history_window` 参数
- 删除 `PERCENTILE_HISTORY_WINDOW`、`compute_total_warmup_bars`；新增 `PERCENTILE_CALENDAR_WINDOW = 365`
- `TOTAL_WARMUP_BARS` 从 495 增至 500，`compute_fetch_start_date` lookback 从 ~704 天增至 731 天
- 更新了 `scripts/compute_trend_features.py`（移除 `--history-window` CLI 参数）
- 更新了 `tests/test_compute_trend_features.py` 以匹配新 API，全部 32 个测试通过
- 修复后 GOOGL NaN 行从 102 降至 4（真实边缘情况）

### Claude (session 4)

- 清空 `feature.db`（`trend_features_daily` 表，6869 行），使旧的行数窗口数据失效
- 用 6 个 ticker（DGRO, JEPI, MSFT, MU, NVDA, SPY）重新训练 v001，截止日 2026-04-14；2928 样本，146 特征，Pearson=0.502
- 验证 GOOGL 推理（2025-01-01 → 2026-04-14）：255 行，0 个 null，从第一天起即有完整预测值，缺口问题彻底消除

### Claude (session 5)

- 创建分支 `feature/closed-loop-backtest`，完善回测闭环
- 修复 JSON 序列化崩溃（`date` 对象不可序列化 → `_to_json_safe()`）
- 修复现金未扣除 bug（`apply_filled_trade` 用历史 trade_time 做快照时间，reset 快照时间更晚 → 改为 `datetime.now()`）
- 修复账户未重置问题（每次回测强制 `reset_for_backtest()`，清空 positions + trade_records）
- 新增卖出逻辑：downtrend → `action_bias=sell_bias`，signal 生成卖出信号，engine 在日内 high 触价时全仓成交
- `config/backtest.yaml` 补充策略默认参数
- `metrics` 新增 `sell_trades` 字段
- 验证：SPY 2025 全年 → 14 笔买入，现金 91163，持仓市值 9618，收益 +0.78%，32 个测试全过
- PR 已提交：`feature/closed-loop-backtest` → `main`

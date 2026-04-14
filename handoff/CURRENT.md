# Current Status

Last updated: 2026-04-14
Owner: Shared between Claude (day) and Codex (night)

## Active Goal

回测闭环已完成并合并（commit `e63bdca`）。下一步：实现 ML 信号接入——将 `pred_strength_pct` 作为与 trend 平行的信号传入 `generate_daily_signal`，用于买入门控和金额缩放。

## Confirmed Project State

- Foundation、数据层、账户、趋势引擎、ML 子系统全部就绪
- **All 32 tests pass** (`python -m pytest -q`)
- `feature.db` 目前为空（2026-04-14 清空；需重新跑 `compute_trend_features`）
- `buy/v001` 模型已用 6 个 ticker（DGRO JEPI MSFT MU NVDA SPY）重训，截止 2026-04-14
- 回测闭环：JSON 修复、账户重置、现金扣除修复、卖出逻辑均已合并到 main

## 下一个任务：ML 信号接入

新开分支 `feature/ml-signal-integration`。

### 架构

```
compute_ma_features → classify_trend ──────────┐
                                                ├→ generate_daily_signal → fill
strength_lookup[date] (pred_strength_pct) ─────┘
```

两个信号平行进入 `generate_daily_signal`，由它统一决策。engine 不做 ML 判断，只透传。

### 规则

- `pred_strength_pct < 0.8`：不买（hold，reason=`hold:ml_strength_below_threshold`）
- `0.8 ≤ pred_strength_pct ≤ 1.0`：`ml_multiplier = 0.5 + (pct - 0.8) * 5.0`，乘以 `final_amount_usd`
- `pred_strength_pct = None`（ML 未启用或无预测）：行为不变，向后兼容

### 文件变更范围

| 文件 | 操作 |
|------|------|
| `app/backtest/ml_bridge.py` | 新建：`compute_backtest_strength_lookup(ticker, start_date, end_date, config) -> dict[str, float]` |
| `app/trend/signal.py` | 加 `ml_strength_pct: float | None = None` 参数，内部做门控与缩放 |
| `app/backtest/engine.py` | 循环前调 ml_bridge，循环内透传 `ml_strength_pct` |
| `tests/test_backtest_ml_integration.py` | 新建：测试门控/缩放逻辑 |

### ml_bridge 关键逻辑

```python
# app/backtest/ml_bridge.py
def compute_backtest_strength_lookup(ticker, start_date, end_date, config) -> dict[str, float]:
    if not config.get("ml", {}).get("enabled"):
        return {}
    model_version = config["ml"]["buy_model_version"]   # e.g. "buy/v001"
    # 1. update_feature_db(ticker, compute_fetch_start_date(start_date), end_date, feature_db_path)
    # 2. load_feature_rows(ticker, start_date, end_date, feature_db_path)
    # 3. load model artifacts from models/buy/{version}/
    # 4. predict_strength_pct(feature_df, model_params)
    # 5. return {date_str: pred_pct}  filtered to [start_date, end_date]
```

### signal.py 关键逻辑

在 `can_buy` 判断通过之后、return buy signal 之前：

```python
if can_buy and ml_strength_pct is not None:
    if ml_strength_pct < 0.8:
        can_buy = False
        # fall through to hold return with reason="hold:ml_strength_below_threshold"
    else:
        ml_multiplier = 0.5 + (ml_strength_pct - 0.8) * 5.0
        budget = {**budget, "final_amount_usd": budget["final_amount_usd"] * ml_multiplier}
```

## Last Known Useful Commands

```bash
python -m pytest -q
python scripts/run_backtest.py --config config/backtest.yaml --ticker SPY --start-date 2025-01-01 --end-date 2025-12-31 --output outputs/backtest_spy_2025.json
python scripts/train_buy_sub_ml.py --tickers DGRO JEPI MSFT MU NVDA SPY --end-date 2026-04-14 --mode new --model v001
python scripts/infer_buy_sub_ml.py --tickers GOOGL --start-date 2025-01-01 --end-date 2026-04-14 --mode infer --model buy/v001
```

## Session End Checklist

- update this file if the active goal changes
- record the latest failing or passing command
- leave the next action in a single sentence

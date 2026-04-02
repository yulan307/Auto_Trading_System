# Minimal Closed Loop（最小闭环）执行计划与策略定义

## 1. 目标

在当前代码基础上，优先完成可运行的回测闭环：

1. 从本地 `daily_bars` 读取历史数据
2. 计算趋势特征并生成日级信号
3. 用最简成交规则模拟买入成交
4. 更新虚拟账户与持仓
5. 输出回测结果 JSON 与日志

> 范围刻意保持最小化：只做买入，不做卖出，不接入真实 broker。

---

## 2. 执行计划（按顺序）

### 步骤 A：脚本入口（含数据初始化）

- 实现 `scripts/run_backtest.py`
- 参数：`--config --ticker --start-date --end-date --output`
- 启动后自动：
  - 初始化 runtime
  - 初始化数据库
  - 执行回测前数据初始化 `_ensure_daily_data_ready`：
    - 若 `data.daily_provider=yfinance`：自动拉取并写入 `daily_bars`
    - 若 `data.daily_provider=local`：检查本地数据库是否已有区间数据
  - 调用 `app.backtest.engine.run_backtest`
  - 将结果写入 JSON

### 步骤 B：回测主循环

- 在 `app/backtest/engine.py` 实现最小主循环
- 使用 `daily_bars` 的 OHLC 数据逐日推进
- 仅当可计算 MA60 slope 后（第 63 根开始）产生趋势决策

### 步骤 C：最简推荐策略（填补“未定义核心策略”）

#### 策略名

`trend_rebound_minimal`

#### 规则定义

1. **趋势判定**：沿用当前 `trend/features.py + trend/classifier.py`
2. **日级买入信号**：沿用 `trend/signal.py`
3. **成交触发（最简）**：
   - 若当日 `daily_signal.action == buy`
   - 且 `daily_signal.target_price` 存在
   - 且当日 `low <= target_price`
   - 则判定“当日触发限价买入成交”，成交价 = `target_price`
4. **下单金额**：使用 `daily_signal.final_amount_usd`
5. **数量规则**：
   - 若不允许碎股：`quantity = floor(amount / price)`
   - 若允许碎股：`quantity = amount / price`
6. **手续费**：最小闭环版本固定 `0`
7. **卖出**：本版本不实现

### 步骤 D：输出指标

输出最小指标：

- `bars`
- `decision_days`
- `buy_trades`
- `final_cash`
- `marked_market_value`（最后一根 close 对持仓估值）
- `final_asset_estimate`
- `total_return_pct`

### 步骤 E：文档与验证

- 文档化使用说明
- 增加测试，保证闭环可运行

---

## 3. 使用说明

## 3.1 初始化数据库

```bash
python scripts/init_db.py --config config/backtest.yaml
```

## 3.2 准备数据

回测初始化会自动确保数据在场：

- 当 `data.daily_provider=yfinance`：自动拉取 `--start-date ~ --end-date` 数据并入库
- 当 `data.daily_provider=local`：要求本地 `daily_bars` 已有对应数据，否则会直接报错

## 3.3 运行最小闭环回测

```bash
python scripts/run_backtest.py \
  --config config/backtest.yaml \
  --ticker SPY \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --output outputs/backtest_minimal_spy.json
```

## 3.4 输出说明

- 控制台输出：`status` 与输出路径
- JSON 输出：
  - `trades`: 成交记录（仅 buy）
  - `decisions`: 每日趋势 + 信号
  - `metrics`: 最小绩效指标

---

## 4. 已知限制（MVP）

1. 无卖出引擎，仓位可能持续累积
2. 无滑点、无手续费、无停牌/涨跌停处理
3. 成交逻辑仅用日线 `low` 触发，未接入 15m 回放
4. 未接入真实 broker/account

建议在本最小闭环稳定后，下一阶段优先补：卖出规则、手续费模型、日内成交回放。

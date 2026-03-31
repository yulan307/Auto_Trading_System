# Daily Signal

## 目标

把趋势输出与预算输出汇总成单一的当日可执行信号对象，作为 Trend Engine 与 Intraday Engine 之间的正式桥梁。

## 输入

- `latest_daily_row`
- `TrendDecision`
- `SymbolInfo`
- `AccountSnapshot`
- `Position | None`
- `RecentTradeStats`

## 输出

- `DailySignal`

## 核心逻辑

### action 允许值

首版只允许：

- `buy`
- `hold`

### buy 前提条件

必须同时满足：

- `action_bias == "buy_bias"`
- `buy_threshold_pct` 有值
- `rebound_pct` 有值
- `final_amount_usd > 0`

### target_price 定义

首版固定：

`base_price = min(open, close)`

`target_price = base_price * (1 - buy_threshold_pct)`

### hold 规则

任一关键条件不满足则 `hold`

### target_price 下游约束

若 `action == hold`，则：

- `target_price = None`

## 状态变量

- `base_price`
- `buy_threshold_pct`
- `rebound_pct`
- `allowed_cash_today`
- `planned_amount_usd`
- `final_amount_usd`

## 边界条件

- 趋势不允许买入
- 趋势阈值缺失
- 预算结果为 0
- `target_price <= 0`

## MVP范围

- 只做 `buy/hold`
- 不做 sell signal
- 不做分位或波动率过滤

## 测试方案

- `rebound_setup` 生成买入信号测试
- 趋势不允许买入时 hold 测试
- 预算耗尽时 hold 测试
- `target_price` 计算测试

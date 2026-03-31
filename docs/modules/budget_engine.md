# Budget Engine

## 目标

在生成 `DailySignal` 前，根据标的配置、账户状态、持仓和最近交易统计，计算当日允许资金与最终下单金额。

## 输入

- `SymbolInfo`
- `AccountSnapshot`
- `Position | None`
- `RecentTradeStats`
- `TrendDecision`

## 输出

- `allowed_cash_today`
- `planned_amount_usd`
- `final_amount_usd`
- `reason`

## 核心逻辑

### 基础预算层

- `daily_base_budget = base_trade_amount_usd`
- `weekly_total_budget = daily_base_budget * weekly_budget_multiplier`

### 约束层

- 本周剩余预算
- 持仓剩余空间
- 可用现金

### 今日可用资金

`allowed_cash_today = min(daily_base_budget, remaining_weekly_budget, remaining_position_capacity, cash_limit)`

### 趋势资金系数

来自 `TrendDecision.budget_multiplier`

### 最终金额裁剪

`final_amount_usd` 再次被周预算、持仓空间和现金约束裁剪

### 最小交易门槛

首版固定：

- `MIN_TRADE_AMOUNT_USD = 50`

## 状态变量

- `daily_base_budget`
- `weekly_total_budget`
- `remaining_weekly_budget`
- `remaining_position_capacity`
- `cash_limit`

## 边界条件

- 已到最大持仓
- 本周预算耗尽
- 无可用现金
- 趋势系数为 0
- 最终金额小于最小交易门槛

## MVP范围

- buy 方向
- 单 ticker
- 单账户
- 不覆盖卖出仓位管理和组合预算

## 测试方案

- 强趋势正常分配测试
- 本周额度耗尽测试
- 持仓上限达到测试
- 小额交易被拒绝测试

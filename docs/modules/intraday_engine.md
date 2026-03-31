# Intraday Engine

## 目标

在 `DailySignal` 已给出 `buy/hold`、`target_price` 和计划金额的前提下，基于 15 分钟数据决定何时追踪、下单、撤单和强制成交。

## 输入

- `DailySignal`
- `TrendDecision.rebound_pct`
- `SymbolInfo.allow_force_buy_last_bar`
- 15 分钟 bar 数据

## 输出

- `IntradayState`
- 下单 / 撤单事件
- 当日执行结果

## 核心逻辑

### tracked_low 规则

- `tracked_low` 代表从开盘到当前 bar 为止的全日最低价
- 首根 bar 初始化
- 出现更低 low 时更新

### 反弹确认

若：

- `tracked_low <= target_price`
- `(close - tracked_low) / tracked_low >= rebound_pct`

则触发下单。

### 下单价格

首版 `limit buy`：

`limit_price = min(current_bar.close, target_price)`

### 撤单规则

若已有活动订单，后续又出现更低点：

- 先检查是否已成交
- 未成交则撤单
- 继续追踪

### force buy

最后一根 15 分钟 bar，若仍未成交且收盘价不高于目标价，可触发 `market buy`

## 状态变量

- `tracked_low`
- `tracked_low_time`
- `current_order_id`
- `order_active`
- `entered_trade`
- `order_submit_price`
- `order_submit_time`

## 边界条件

- 日级信号不是 `buy`
- 全日最低价未触达目标价
- 活动订单状态不同步
- 尾盘仍未成交

## MVP范围

- buy 方向
- 同 ticker 同交易日最多一次成交
- 不实现卖出、黑天鹅、partial fill

## 测试方案

- tracked_low 更新测试
- rebound 触发下单测试
- 更低点触发撤单测试
- 最后一根 bar force buy 测试

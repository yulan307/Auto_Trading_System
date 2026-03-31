# Backtest Fill

## 目标

统一定义回测环境中的订单成交时点、成交价格和订单生命周期，保证回测行为固定、可复现。

## 输入

- 当前 bar
- `OrderRequest` / `OrderStatus`

## 输出

- 更新后的 `OrderStatus`
- 成交价格与成交时间

## 核心逻辑

### 核心原则

- 不猜测 bar 内完整路径
- 使用固定保守规则
- `market` 单可在当前 bar 立即成交
- `limit` 单允许在提交所在 bar 判断成交

### market buy

- 成交价：`bar.close`
- 成交时间：`bar.datetime`

### limit buy

- 若 `bar.low <= submitted_price` 则成交
- 成交价固定为 `submitted_price`
- 否则维持 `submitted`

### 撤单与成交优先级

每根后续 bar 内：

1. 先检查是否成交
2. 再检查是否撤单
3. 再决定是否提交新单

### 收盘未成交

- 订单状态：`expired_end_of_day`
- 不允许跨日保留

## 状态变量

- `submitted_price`
- `avg_fill_price`
- `filled_quantity`
- `filled_amount`
- `status`

## 边界条件

- `quantity <= 0`
- `limit` 单无价格
- 最后一根 bar 未成交
- 同 ticker 同交易日重复成交

## MVP范围

- 单日 15 分钟 bar
- buy 方向
- `market` / `limit`
- 不做 partial fill、queue、volume constraint

## 测试方案

- market buy 成交测试
- limit buy 同 bar 成交测试
- limit buy 未成交测试
- 收盘过期测试

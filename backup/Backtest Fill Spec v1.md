# 回测成交规则规范（Backtest Fill Spec v1）

## 1. 目标

定义回测环境中订单如何成交、何时成交、按什么价格成交。
该规范用于统一：

* Intraday Engine
* Execution Engine
* Backtest Engine

要求：

* 规则固定
* 可复现
* 不依赖主观解释
* 首版尽量简单，但不能自相矛盾

---

## 2. 适用范围

本规范首版只覆盖：

* 单日内 15min bar 回测
* buy 方向
* market / limit 两种订单
* 单 ticker 单日最多一次成交

本规范首版不覆盖：

* sell
* stop order
* stop limit
* trailing stop
* partial fill
* 同一时刻多个订单竞争
* bar 内逐笔路径模拟

---

## 3. 输入对象

## 3.1 bar 数据

每根 15min bar 必须包含：

```python
- datetime
- open
- high
- low
- close
- volume
```

约束：

* 同一交易日内升序排列
* 不允许重复
* 不允许缺失 OHLC

---

## 3.2 订单对象

```python
OrderRequest:
- ticker
- side            # buy
- order_type      # market / limit
- price           # limit 时必须有值
- amount_usd
- quantity
- reason
```

---

## 3.3 订单状态对象

```python
OrderStatus:
- order_id
- ticker
- side
- status
- submit_time
- update_time
- submitted_price
- avg_fill_price
- filled_quantity
- filled_amount
- broker_message
```

---

## 4. 回测核心原则

## 4.1 不猜测 bar 内完整路径

首版不假设：

* 先到 high 再到 low
* 先到 low 再到 close
* 任意更细粒度路径

只允许使用已知事实：

```text
bar.open, bar.high, bar.low, bar.close
```

---

## 4.2 成交规则必须偏保守，但不能过度悲观

原则：

* 不使用对策略有利但无法证明的成交价
* 不用“最优成交”
* 不用“随机成交”
* 用固定规则近似

---

## 4.3 提交后，从“下一步可判定时点”开始判断成交

这是首版最重要的统一约定：

### 订单在某根 bar 上被提交时：

* 若是 **market order**：允许在当前 bar 立即成交
* 若是 **limit order**：首版允许在当前 bar 按规则判断成交

原因：

* 你的日内逻辑本身就是基于 bar close / bar 状态生成信号
* 若完全推迟到下一根 bar，会使首版过于迟滞

但必须配套一个固定保守价规则，避免高估收益。

---

## 5. market buy 成交规则

若在当前 bar 触发 `market buy`：

```text
直接成交
```

成交价定义为：

```python
fill_price = current_bar.close
```

成交时间定义为：

```python
fill_time = current_bar.datetime
```

说明：

* 首版假设 market 单在 bar 结束时触发并成交
* 不用 open，不用 high，不用 low
* 用 close 最一致

---

## 6. limit buy 成交规则

若提交 limit buy，设：

```python
limit_price = submitted_price
```

则判断规则为：

### 6.1 可成交条件

若当前 bar 满足：

```text
bar.low <= limit_price
```

则认为该 limit buy 在该 bar 内可成交。

---

### 6.2 成交价规则

首版固定为：

```python
fill_price = limit_price
```

不因：

* bar.open 更低
* bar.low 更低
* bar.close 更低

而改善成交价。

这是一条重要保守规则。

---

### 6.3 不可成交条件

若：

```text
bar.low > limit_price
```

则该 bar 不成交，订单继续保持 active。

---

## 7. limit buy 提交所在 bar 的处理

若 limit buy 是在当前 bar 触发提交的，则首版允许立刻用该 bar 判断是否成交：

### 规则：

1. 先根据当前 bar 生成信号
2. 再生成 limit order
3. 再用当前 bar 的 low 判断是否成交

即：

```text
signal generation → order submit → fill check on same bar
```

这是首版的统一时序。

---

## 8. 撤单规则与成交判断顺序

若某根 bar 中既可能触发撤单，也可能已经成交，则顺序必须固定。

统一顺序：

### 每根后续 bar 的处理顺序：

```text
1. 先检查活动订单是否成交
2. 若已成交 → 当日结束
3. 若未成交，再检查是否出现新低导致撤单
4. 若满足撤单 → 执行撤单
5. 若没有活动订单，再判断是否生成新订单
```

这条顺序不能改变。

原因：

* 避免“其实已经成交，却被误撤单”
* 保持逻辑稳定

---

## 9. force buy 的回测规则

若最后一根 bar 触发 force buy：

```text
order_type = market
```

则按 market buy 规则处理：

```python
fill_price = last_bar.close
fill_time = last_bar.datetime
```

立即成交。

---

## 10. quantity 计算规则

设：

```python
raw_qty = amount_usd / fill_reference_price
```

其中：

* market 单：`fill_reference_price = current_bar.close`
* limit 单：`fill_reference_price = limit_price`

然后：

### 若允许碎股

```python
quantity = raw_qty
```

### 若不允许碎股

```python
quantity = floor(raw_qty)
```

---

## 11. 无法下单的判定

若 quantity 计算后：

```text
quantity <= 0
```

则该订单直接拒绝，返回：

```text
status = "rejected"
reason = "quantity_too_small"
```

并记日志。

---

## 12. filled_amount 定义

```python
filled_amount = fill_price * filled_quantity
```

首版不额外加入税费与滑点。

---

## 13. 手续费规则（首版）

首版默认：

```python
fee = 0.0
```

但必须保留接口：

```python
def calculate_fee(order, fill_price, filled_quantity) -> float:
    ...
```

后续可扩展：

* fixed fee
* per-share fee
* min/max fee
* broker-specific fee

---

## 14. 滑点规则（首版）

首版默认：

```python
slippage = 0.0
```

但必须保留配置项：

```yaml
backtest:
  slippage_mode: none
  slippage_value: 0.0
```

后续可扩展：

* fixed bps
* fixed cents
* volatility-based slippage

---

## 15. 活动订单生命周期

订单状态流转首版统一为：

```text
submitted
→ filled
或
submitted → canceled
或
submitted → expired_end_of_day
或
rejected
```

---

## 16. 收盘未成交订单处理

若到当日最后一根 bar 结束后，limit 单仍未成交，且未触发 force buy，则：

```text
status = "expired_end_of_day"
```

说明：

* 首版不允许订单跨日保留
* 次日必须重新根据新信号决定是否下单

---

## 17. 同日只允许一次成交

首版规则：

```text
每个 ticker 每个交易日最多一笔 filled trade
```

因此：

* 一旦 `entered_trade == True`
* 后续所有 bar 不再生成新订单

---

## 18. 事件优先级

同一根 bar 内若有多个可能事件，优先级如下：

```text
1. filled
2. cancel
3. submit new order
4. force buy
5. finish unfilled
```

注意：

* `force buy` 只在最后一根 bar 且无活动订单时才触发
* 已有活动订单时，不能同时再 force buy

---

## 19. 回测结果必须记录的字段

每次订单事件至少记录：

```python
- ticker
- trade_date
- bar_time
- event_type
- order_id
- order_type
- submitted_price
- fill_price
- quantity
- amount
- status
- reason
```

---

## 20. 回测引擎调用接口建议

```python
def simulate_order_fill_on_bar(
    order_status: OrderStatus,
    bar,
) -> OrderStatus:
    ...
```

行为：

* 输入活动订单与当前 bar
* 输出更新后的订单状态

---

## 21. 伪代码

```python
if order_type == "market" and side == "buy":
    fill_price = bar.close
    status = "filled"

elif order_type == "limit" and side == "buy":
    if bar.low <= submitted_price:
        fill_price = submitted_price
        status = "filled"
    else:
        status = "submitted"
```

---

## 22. 首版限制总结

本版本明确不做：

* partial fill
* bar 内更细路径
* price improvement
* queue position
* liquidity impact
* volume constraint
* overnight carry

首版核心思想：

```text
固定规则 > 复杂但不稳定的拟真
```

---

## 23. 与其他模块的边界

### Intraday Engine 负责：

* 何时提交订单
* 何时撤单
* 何时停止追踪

### Backtest Fill Spec 负责：

* 订单一旦提交，在 bar 上是否成交
* 成交价格是多少
* 未成交如何继续存活或失效

### Execution Engine 负责：

* 记录订单状态
* 更新账户
* 输出成交结果

---


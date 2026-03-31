# 日内交易模块规范（Intraday Engine Spec v1）

## 1. 目标

在日级信号已经给出 `action / target_price / planned_amount_usd / rebound_pct` 的前提下，
使用 15min 数据决定：

* 是否进入追踪
* 何时下单
* 何时撤单
* 何时强制成交
* 当日何时结束

该模块必须满足：

* 可回测
* 可复现
* 可迁移到 paper / live
* 不依赖主观判断

---

## 2. 输入定义

## 2.1 来自 DailySignal

```python
DailySignal:
- trade_date
- ticker
- action                  # buy / sell / hold
- target_price            # 买入目标价
- final_amount_usd        # 当日计划使用金额
- reason
```

仅当：

```text
action == "buy"
```

才进入本模块。

---

## 2.2 来自 TrendDecision

```python
TrendDecision:
- trend_type
- rebound_pct
- budget_multiplier
```

其中本模块直接使用：

* `rebound_pct`

---

## 2.3 来自 SymbolInfo

```python
SymbolInfo:
- allow_force_buy_last_bar
- allow_fractional
```

---

## 2.4 15min bar 数据

每根 bar 必须至少包含：

```python
- datetime
- open
- high
- low
- close
- volume
```

要求：

* 已按时间升序排列
* 全部属于同一交易日
* 不允许缺失 datetime
* 不允许重复 bar

---

## 3. 模块输出

模块输出统一为：

```python
IntradayExecutionResult:
- ticker: str
- trade_date: str
- action: str                     # buy / hold
- status: str                     # filled / unfilled / skipped / canceled
- order_count: int
- cancel_count: int
- filled_price: float | None
- filled_quantity: float | None
- filled_amount: float | None
- fill_bar_time: datetime | None
- exit_reason: str
- note: str | None
```

---

## 4. 日内状态对象

```python
IntradayState:
- ticker: str
- trade_date: str
- tracking_side: str              # buy
- tracked_low: float | None
- tracked_high: float | None
- tracked_low_time: datetime | None
- current_order_id: str | None
- order_active: bool
- entered_trade: bool
- force_trade_enabled: bool
- order_submit_price: float | None
- order_submit_time: datetime | None
- order_type: str | None          # limit / market
- last_bar_time: datetime | None
- note: str | None
```

首版只实现 `buy`。

---

## 5. 运行流程总览

对当日全部 15min bar 依次循环：

1. 初始化 state
2. 更新 tracked_low
3. 判断是否满足反弹确认
4. 若满足 → 生成买单
5. 若已有挂单 → 检查是否需要撤单
6. 若订单成交 → 结束当日
7. 若进入最后 15 分钟且仍未成交 → 判断是否 force buy
8. 若到收盘仍未成交 → 返回 unfilled

---

## 6. 初始化规则

```python
def init_intraday_state(ticker: str, trade_date: str, force_trade_enabled: bool) -> IntradayState:
    ...
```

初始化值：

```python
tracked_low = None
tracked_high = None
tracked_low_time = None
current_order_id = None
order_active = False
entered_trade = False
order_submit_price = None
order_submit_time = None
order_type = None
last_bar_time = None
```

---

## 7. tracked_low 更新规则

## 7.1 首根 bar

若 `tracked_low is None`：

```text
tracked_low = current_bar.low
tracked_low_time = current_bar.datetime
```

---

## 7.2 后续 bar

若：

```text
current_bar.low < tracked_low
```

则：

```text
tracked_low = current_bar.low
tracked_low_time = current_bar.datetime
```

并记录事件：

```text
event = "new_low_detected"
```

---

## 7.3 关键原则

tracked_low 永远表示：

```text
从当日开始到当前 bar 为止出现过的最低 low
```

不是最近几根 bar 的局部低点。

---

## 8. 买入前置条件

只有同时满足以下条件，才允许进入“下单判断”：

### 条件 A：价格曾进入目标区

```text
tracked_low <= target_price
```

说明：

* 如果全天最低价都没有到达目标价
* 则不允许买入

---

### 条件 B：当前尚未成交

```text
entered_trade == False
```

---

### 条件 C：当前无已成交终止状态

```text
status not in ["filled", "done"]
```

---

## 9. 反弹确认规则（核心）

定义：

```python
rebound_from_low = (current_bar.close - tracked_low) / tracked_low
```

若同时满足：

```text
tracked_low <= target_price
AND rebound_from_low >= rebound_pct
AND current_bar.close >= tracked_low
```

则触发：

```text
event = "place_order"
```

---

## 10. 下单价格规则

首版下单价格定义如下：

## 10.1 limit buy 价格

```python
limit_price = min(current_bar.close, target_price)
```

解释：

* 反弹确认后，不追高到 target_price 以上
* 若当前 close 已高于 target_price，则只挂 target_price
* 若当前 close 仍低于 target_price，则按当前 close 近似挂单

---

## 10.2 order_request 构造

```python
OrderRequest(
    ticker=ticker,
    side="buy",
    order_type="limit",
    price=limit_price,
    amount_usd=final_amount_usd,
    quantity=None,
    reason="intraday rebound confirmed"
)
```

---

## 11. 下单后状态更新

下单后更新 state：

```text
order_active = True
current_order_id = broker returned order_id
order_submit_price = limit_price
order_submit_time = current_bar.datetime
order_type = "limit"
```

---

## 12. 撤单规则（核心）

若已经存在活动订单：

```text
order_active == True
```

则每根后续 bar 都要检查是否撤单。

---

## 12.1 撤单条件

若当前 bar 出现：

```text
current_bar.low < tracked_low_before_this_bar
```

说明：

* 市场又创新低
* 之前的“低点已确认”判断失效

此时：

### 若订单未成交

执行：

```text
cancel_order(current_order_id)
order_active = False
current_order_id = None
order_submit_price = None
order_submit_time = None
order_type = None
event = "cancel_order"
```

并继续进入追踪模式。

---

## 12.2 若订单已成交

若检查订单状态为 `filled`：

```text
entered_trade = True
event = "done"
```

直接结束当日。

---

## 13. 成交判断规则（给回测引擎使用）

首版 limit buy 成交规则统一定义为：

若某根 bar 满足：

```text
bar.low <= order_submit_price
```

则认为该单在该 bar 内成交。

成交价统一定义为：

```python
fill_price = order_submit_price
```

说明：

* 首版不模拟更细粒度撮合
* 不做 bar 内路径猜测
* 不优化成交价

---

## 14. force buy 规则

## 14.1 触发时点

最后一根 15min bar 视为：

```text
last tradable bar
```

首版约定：

* 当循环进入当日最后一根 15min bar 时，允许触发 force buy

---

## 14.2 force buy 条件

同时满足：

```text
allow_force_buy_last_bar == True
AND entered_trade == False
AND order_active == False
AND current_bar.close <= target_price
```

则触发：

```text
event = "force_buy"
```

并生成：

```python
OrderRequest(
    ticker=ticker,
    side="buy",
    order_type="market",
    price=None,
    amount_usd=final_amount_usd,
    quantity=None,
    reason="last bar force buy"
)
```

---

## 14.3 force buy 成交规则

market 单在首版中定义为：

```python
fill_price = current_bar.close
```

立即成交。

---

## 15. 不买入的三种标准结果

## 15.1 skipped_target_not_reached

若全天都满足：

```text
min(day_low) > target_price
```

返回：

```text
status = "skipped"
exit_reason = "target_not_reached"
```

---

## 15.2 unfilled_after_tracking

若曾触发追踪与下单，但最终未成交，返回：

```text
status = "unfilled"
exit_reason = "tracking_finished_without_fill"
```

---

## 15.3 skipped_no_signal

若 `action != buy`，直接不进入模块：

```text
status = "skipped"
exit_reason = "daily_signal_not_buy"
```

---

## 16. 当日结束条件

满足以下任一条件即结束：

1. 订单成交
2. force buy 成交
3. 最后一根 bar 结束后仍未成交
4. 日级信号不是 buy

---

## 17. 日志要求

每个关键事件必须写日志：

* `intraday_init`
* `new_low_detected`
* `rebound_confirmed`
* `order_submit`
* `order_cancel`
* `order_fill`
* `force_buy_submit`
* `intraday_finish`

日志必须至少包含：

* ticker
* trade_date
* bar_time
* tracked_low
* target_price
* rebound_pct
* event
* reason

---

## 18. 首版明确不做的事情

本版本不实现：

* 卖出 intraday 逻辑
* 黑天鹅处理
* bar 内路径推测
* partial fill
* 多订单并存
* 同日多次买入
* 按 volume 判断反弹有效性

首版约束为：

```text
每个 ticker 每天最多只允许一次成交
```

---

## 19. 伪代码

```python
for bar in intraday_bars:
    update tracked_low

    if order_active:
        check fill
        if filled:
            return filled result

    if order_active and new lower low appears:
        check fill again
        if not filled:
            cancel order
            continue

    if not entered_trade and not order_active:
        if tracked_low <= target_price:
            rebound_from_low = (bar.close - tracked_low) / tracked_low
            if rebound_from_low >= rebound_pct:
                place limit buy

    if is_last_bar:
        if not entered_trade and not order_active:
            if allow_force_buy_last_bar and bar.close <= target_price:
                place market buy and return filled
```

---

## 20. 下一步必须补充的内容

下一阶段继续固定：

1. 回测成交规则规范（Backtest Fill Spec）
2. 资金分配规则规范（Budget Spec）
3. 分位系统规范（Pullback Percentile Spec）

其中优先级最高的是：

```text
Backtest Fill Spec
```

因为它决定你的回测结果是否可信。

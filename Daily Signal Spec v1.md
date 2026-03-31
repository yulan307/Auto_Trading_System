# Daily Signal 生成规范（Daily Signal Spec v1）

## 1. 目标

将以下输入统一汇总为**当日可执行信号**：

* 最新日线数据
* TrendDecision
* SymbolInfo
* AccountSnapshot
* Position
* RecentTradeStats

输出唯一标准对象：

* `DailySignal`

该模块是：

```text
Trend Engine → Budget Engine → Daily Signal → Intraday Engine
```

之间的正式桥梁。

要求：

* 可回测
* 可复现
* 无隐式判断
* 所有 reason 必须可追踪

---

## 2. 输入对象

## 2.1 latest_daily_row

至少包含：

```python
- trade_date
- open
- high
- low
- close
```

说明：

* `trade_date` 为当前生成信号对应日期
* DailySignal 用于“下一交易日盘中执行”
* 但首版回测中可简化为：用该交易日开盘前已知的历史信息生成该日信号

---

## 2.2 TrendDecision

必须包含：

```python
TrendDecision:
- trade_date
- ticker
- trend_type
- trend_strength
- action_bias
- buy_threshold_pct
- rebound_pct
- budget_multiplier
- reason
```

---

## 2.3 SymbolInfo

必须包含：

```python
SymbolInfo:
- symbol
- base_trade_amount_usd
- max_position_usd
- weekly_budget_multiplier
- allow_force_buy_last_bar
- allow_fractional
```

---

## 2.4 AccountSnapshot

必须包含：

```python
AccountSnapshot:
- cash_available
- market_value
- total_asset
```

---

## 2.5 Position

```python
Position | None
```

若无持仓，则视为：

```text
position = None
```

---

## 2.6 RecentTradeStats

```python
{
    "ticker": ...,
    "buy_count_5d": ...,
    "buy_amount_5d": ...,
    "sell_count_5d": ...,
    "sell_amount_5d": ...,
    "trade_count_week": ...,
    "trade_amount_week": ...,
}
```

---

## 3. 输出对象

```python
from dataclasses import dataclass
from datetime import date

@dataclass
class DailySignal:
    trade_date: date
    ticker: str
    action: str                # buy / sell / hold
    target_price: float | None
    planned_amount_usd: float
    allowed_cash_today: float
    final_amount_usd: float
    reason: str
```

---

## 4. 模块职责边界

### Daily Signal 模块负责：

* 判断今天是否值得进入 intraday
* 给出 `buy / hold`
* 给出 `target_price`
* 给出 `planned_amount_usd / final_amount_usd`

### 不负责：

* 日内低点追踪
* 撤单
* force buy 执行
* 成交判断
* 卖出执行细节

---

## 5. action 允许值

首版仅允许：

```text
buy
hold
```

说明：

* `sell` 接口暂不启用
* 卖出逻辑后续独立补充

---

## 6. 首版 action 决策规则

## 6.1 默认原则

若任一关键条件不满足，默认：

```text
action = hold
```

系统必须偏保守。

---

## 6.2 允许 buy 的前提条件

只有同时满足以下条件，才允许：

```text
trend_decision.action_bias == "buy_bias"
AND trend_decision.buy_threshold_pct is not None
AND trend_decision.rebound_pct is not None
AND final_amount_usd > 0
```

否则：

```text
action = hold
```

---

## 7. target_price 定义（核心）

首版统一使用以下基准价：

```python
base_price = min(latest_daily_row.close, latest_daily_row.open)
```

然后定义：

```python
target_price = base_price * (1 - buy_threshold_pct)
```

说明：

* 用 `min(open, close)` 而不是单用 close
* 是为了减少跳空高开对目标价的干扰
* 与你前面讨论过的跌幅基准思想一致

---

## 8. 为什么使用 min(open, close)

定义：

```text
base_price = min(today_open, yesterday_close-like reference simplified to latest row open/close)
```

首版由于 DailySignal 使用当日行数据，先采用：

```python
min(open, close)
```

后续若你要更严格，可升级为：

```python
base_price = min(prev_close, today_open)
```

但那需要把数据接口明确成“上一日 close + 当日 open”。

### 因此首版固定：

```python
base_price = min(latest_daily_row.open, latest_daily_row.close)
```

---

## 9. target_price 合法性约束

若计算后：

```text
target_price <= 0
```

则视为非法，输出：

```text
action = hold
reason = "invalid_target_price"
```

---

## 10. 预算接入规则

Daily Signal 模块必须调用 Budget Spec 的两个接口：

```python
allowed_cash_today, budget_reason_1 = compute_allowed_cash_today(...)
planned_amount_usd, final_amount_usd, budget_reason_2 = compute_final_trade_amount(...)
```

然后再决定 action。

---

## 11. action 最终判定顺序

统一顺序如下：

### Step 1

若 `trend_decision.action_bias != "buy_bias"`：

```text
action = hold
reason = "trend_not_buy_bias"
```

---

### Step 2

若 `buy_threshold_pct is None` 或 `rebound_pct is None`：

```text
action = hold
reason = "trend_threshold_missing"
```

---

### Step 3

计算预算。

若：

```text
final_amount_usd <= 0
```

则：

```text
action = hold
reason = budget_reason
```

---

### Step 4

计算 `target_price`

若非法：

```text
action = hold
reason = "invalid_target_price"
```

---

### Step 5

若以上全部通过：

```text
action = buy
reason = combined_reason
```

---

## 12. combined_reason 组成规则

首版 reason 使用字符串拼接，必须同时保留：

* 趋势原因
* 预算原因
* 目标价原因（若有）

### 示例

```text
"buy_bias | rebound_setup | base_price=min(open,close)=432.1 | buy_threshold_pct=0.018 | target_price=424.32 | final_amount_usd=1300"
```

若 hold，则 reason 示例：

```text
"hold | weekly_budget_exhausted"
```

---

## 13. planned_amount_usd 与 final_amount_usd 的区别

### planned_amount_usd

表示：

```text
趋势模型按强弱主观想买多少
```

### final_amount_usd

表示：

```text
经过预算 / 持仓 / 现金 / 周额度裁剪后，实际允许买多少
```

两者都必须保留，不能只保留 final。

---

## 14. target_price 与 intraday 的关系

DailySignal 只输出：

```text
target_price
```

Intraday Engine 负责判断：

* 日内最低价是否到达
* 是否出现反弹确认
* 是否进入 force buy

因此：

### DailySignal 不负责判断：

* 今日最低价是否已经到了
* 何时反弹
* 何时挂单

---

## 15. 当 trend_type 对应 buy，但 budget 很小

若：

```text
final_amount_usd < MIN_TRADE_AMOUNT_USD
```

则：

```text
action = hold
reason = "trade_amount_below_minimum"
```

此时：

```python
target_price = computed_target_price or None
```

首版建议：

```python
target_price = None
```

因为既然不允许交易，就不需要继续追踪。

---

## 16. hold 状态下 target_price 的处理

首版统一规定：

若：

```text
action == hold
```

则：

```python
target_price = None
```

说明：

* 避免 downstream 模块误进入追踪
* `Intraday Engine` 只接收 action=buy 的信号

---

## 17. action_bias 与 trend_type 的映射约束

首版约定：

```python
buy_bias_trend_types = {
    "strong_uptrend",
    "weak_uptrend",
    "rebound_setup",
}
```

以下默认不买：

```python
non_buy_trend_types = {
    "range",
    "weak_downtrend",
    "strong_downtrend",
}
```

因此 `classify_trend()` 必须保证：

### buy_bias:

* strong_uptrend
* weak_uptrend
* rebound_setup

### hold_bias:

* range
* weak_downtrend
* strong_downtrend

---

## 18. 建议接口

```python
def build_daily_signal(
    latest_daily_row,
    trend_decision: TrendDecision,
    symbol_info: SymbolInfo,
    account_snapshot: AccountSnapshot,
    position: Position | None,
    recent_trade_stats: dict,
) -> DailySignal:
    ...
```

---

## 19. 伪代码

```python
if trend_decision.action_bias != "buy_bias":
    return DailySignal(
        action="hold",
        target_price=None,
        planned_amount_usd=0,
        allowed_cash_today=0,
        final_amount_usd=0,
        reason="trend_not_buy_bias",
    )

allowed_cash_today, reason1 = compute_allowed_cash_today(...)
planned_amount_usd, final_amount_usd, reason2 = compute_final_trade_amount(...)

if final_amount_usd <= 0:
    return DailySignal(
        action="hold",
        target_price=None,
        planned_amount_usd=planned_amount_usd,
        allowed_cash_today=allowed_cash_today,
        final_amount_usd=final_amount_usd,
        reason=reason2,
    )

base_price = min(latest_daily_row.open, latest_daily_row.close)
target_price = base_price * (1 - trend_decision.buy_threshold_pct)

if target_price <= 0:
    return DailySignal(
        action="hold",
        target_price=None,
        planned_amount_usd=planned_amount_usd,
        allowed_cash_today=allowed_cash_today,
        final_amount_usd=final_amount_usd,
        reason="invalid_target_price",
    )

return DailySignal(
    action="buy",
    target_price=target_price,
    planned_amount_usd=planned_amount_usd,
    allowed_cash_today=allowed_cash_today,
    final_amount_usd=final_amount_usd,
    reason="buy_bias | target_price_ready",
)
```

---

## 20. 示例 1：rebound_setup 买入

输入：

```text
trend_type = rebound_setup
action_bias = buy_bias
buy_threshold_pct = 0.02
rebound_pct = 0.01
open = 100
close = 98
allowed_cash_today = 1000
planned_amount_usd = 1300
final_amount_usd = 1300
```

则：

```text
base_price = min(100, 98) = 98
target_price = 98 * (1 - 0.02) = 96.04
action = buy
```

输出：

```text
buy @ target_price=96.04
```

---

## 21. 示例 2：趋势允许买，但预算耗尽

输入：

```text
trend_type = strong_uptrend
action_bias = buy_bias
buy_threshold_pct = 0.015
final_amount_usd = 0
reason = weekly_budget_exhausted
```

则输出：

```text
action = hold
target_price = None
reason = weekly_budget_exhausted
```

---

## 22. 示例 3：range 市场不买

输入：

```text
trend_type = range
action_bias = hold_bias
```

输出：

```text
action = hold
target_price = None
planned_amount_usd = 0
final_amount_usd = 0
reason = trend_not_buy_bias
```

---

## 23. 日志要求

每次生成 DailySignal，必须写日志，至少包含：

* ticker
* trade_date
* trend_type
* trend_strength
* buy_threshold_pct
* rebound_pct
* base_price
* target_price
* allowed_cash_today
* planned_amount_usd
* final_amount_usd
* action
* reason

---

## 24. 首版明确不做的事情

本版本不实现：

* sell signal
* volatility filter
* gap risk adjustment
* percentile-based target price adjustment
* volume confirmation
* macro regime overlay

首版只做：

```text
trend → budget → target_price → buy/hold
```

---

## 25. 当前闭环已经形成

到这里，核心策略闭环已经形成：

```text
Trend Spec v1
→ Budget Spec v1
→ Daily Signal Spec v1
→ Intraday Spec v1
→ Backtest Fill Spec v1
```

这意味着你已经有了**第一版可编码策略核心**。

---


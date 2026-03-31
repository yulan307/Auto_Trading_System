# 资金分配规则规范（Budget Spec v1）

## 1. 目标

定义在 `DailySignal` 生成之前，系统如何根据：

* 标的配置
* 当前账户资金
* 当前持仓
* 过去 5 日交易情况
* 本周累计交易情况
* 趋势状态

计算：

* allowed_cash_today
* final_amount_usd

要求：

* 固定规则
* 可复现
* 不提前透支预算
* 不因单次信号过强而失控

---

## 2. 适用范围

本版本只覆盖：

* buy 方向
* 单 ticker 独立预算
* 现金账户
* 首版单账户

本版本不覆盖：

* sell 仓位管理
* 多账户联动
* 杠杆
* 融资
* 期权保证金
* 组合级风险预算

---

## 3. 输入对象

## 3.1 SymbolInfo

必须至少包含：

```python
SymbolInfo:
- symbol
- base_trade_amount_usd
- max_position_usd
- weekly_budget_multiplier
- allow_fractional
```

---

## 3.2 AccountSnapshot

必须至少包含：

```python
AccountSnapshot:
- cash_available
- market_value
- total_asset
```

---

## 3.3 Position

若该 ticker 当前有持仓：

```python
Position:
- ticker
- quantity
- avg_cost
- market_price
- market_value
```

若无持仓，则视为：

```text
position_market_value = 0
```

---

## 3.4 RecentTradeStats

```python
{
    "ticker": "SPY",
    "buy_count_5d": int,
    "buy_amount_5d": float,
    "sell_count_5d": int,
    "sell_amount_5d": float,
    "trade_count_week": int,
    "trade_amount_week": float,
}
```

---

## 3.5 TrendDecision

必须至少包含：

```python
TrendDecision:
- trend_type
- budget_multiplier
```

---

## 4. 核心理念

本系统资金分配分两层：

### 4.1 长周期预算层

控制：

* 本周最多允许投入多少
* 当前持仓最多允许到多少

### 4.2 当日执行层

控制：

* 今天最多可以买多少
* 单次下单最多买多少

---

## 5. 基础预算定义

## 5.1 单日基准金额

```python
daily_base_budget = symbol_info.base_trade_amount_usd
```

要求：

```text
daily_base_budget > 0
```

---

## 5.2 本周总预算

```python
weekly_total_budget = daily_base_budget * symbol_info.weekly_budget_multiplier
```

约束：

```text
weekly_budget_multiplier >= 1
```

说明：

* 若 `base_trade_amount_usd = 1000`
* `weekly_budget_multiplier = 5`
* 则本周该 ticker 最多投入 5000

---

## 6. 位置上限约束

## 6.1 当前持仓市值

```python
current_position_value = position.market_value if position else 0.0
```

---

## 6.2 剩余持仓空间

```python
remaining_position_capacity = max(
    0.0,
    symbol_info.max_position_usd - current_position_value
)
```

若：

```text
remaining_position_capacity <= 0
```

则当天禁止买入：

```text
allowed_cash_today = 0
reason = "max_position_reached"
```

---

## 7. 本周预算约束

## 7.1 已用本周预算

定义：

```python
used_weekly_budget = recent_trade_stats["buy_amount_5d"]
```

说明：

首版近似用 `buy_amount_5d` 代替“本周已买入金额”。
若后续引入自然周统计，再替换实现，但接口不变。

---

## 7.2 剩余本周预算

```python
remaining_weekly_budget = max(
    0.0,
    weekly_total_budget - used_weekly_budget
)
```

若：

```text
remaining_weekly_budget <= 0
```

则当天禁止买入：

```text
allowed_cash_today = 0
reason = "weekly_budget_exhausted"
```

---

## 8. 现金约束

```python
cash_limit = max(0.0, account_snapshot.cash_available)
```

若：

```text
cash_limit <= 0
```

则当天禁止买入：

```text
allowed_cash_today = 0
reason = "no_cash_available"
```

---

## 9. 当日可用资金 allowed_cash_today

统一定义为三者最小值：

```python
allowed_cash_today = min(
    daily_base_budget,
    remaining_weekly_budget,
    remaining_position_capacity,
    cash_limit,
)
```

说明：

今天最多买多少，首先不能超过：

* 今日基准预算
* 本周剩余额度
* 持仓剩余空间
* 可用现金

---

## 10. 趋势系数映射

来自 `TrendDecision.budget_multiplier`

首版固定为：

```python
trend_budget_map = {
    "strong_uptrend": 1.5,
    "weak_uptrend": 1.2,
    "range": 0.8,
    "weak_downtrend": 0.5,
    "strong_downtrend": 0.2,
    "rebound_setup": 1.3,
}
```

如果 `trend_type` 未命中映射：

```python
budget_multiplier = 0.0
```

即默认不买。

---

## 11. 原始计划买入金额

```python
raw_planned_amount = allowed_cash_today * budget_multiplier
```

---

## 12. 最终买入金额 final_amount_usd

首版为防止单日超买，加入再次裁剪：

```python
final_amount_usd = min(
    raw_planned_amount,
    remaining_weekly_budget,
    remaining_position_capacity,
    cash_limit,
)
```

并再加下限保护：

```python
final_amount_usd = max(0.0, final_amount_usd)
```

---

## 13. 单次最小交易金额门槛

避免出现极小金额导致：

* 下单数量为 0
* 大量无效订单
* 回测噪声

首版定义：

```python
MIN_TRADE_AMOUNT_USD = 50.0
```

若：

```text
final_amount_usd < MIN_TRADE_AMOUNT_USD
```

则：

```text
final_amount_usd = 0
action = hold
reason = "trade_amount_below_minimum"
```

---

## 14. 趋势系数是否允许超过 1

允许。

解释：

* `allowed_cash_today` 是“今日基准层”的保护值
* `budget_multiplier > 1` 表示趋势强时允许稍微提高单日投入
* 但最终仍会被：

  * remaining_weekly_budget
  * remaining_position_capacity
  * cash_limit
    再次裁剪

因此不会失控。

---

## 15. 日内是否允许多次加仓

首版不允许。

因此：

```text
同一 ticker 同一交易日一旦 filled
不再重复计算第二次 final_amount_usd
```

---

## 16. DailySignal 中相关字段定义

生成 `DailySignal` 时：

```python
planned_amount_usd = raw_planned_amount
allowed_cash_today = allowed_cash_today
final_amount_usd = final_amount_usd
```

说明：

* `planned_amount_usd` 表示趋势模型主观想买多少
* `final_amount_usd` 表示规则裁剪后实际允许买多少

这样方便调试与日志审计。

---

## 17. 禁止买入的标准原因

当 `final_amount_usd == 0` 时，必须明确写出 reason，首版允许值：

```text
max_position_reached
weekly_budget_exhausted
no_cash_available
trade_amount_below_minimum
trend_multiplier_zero
```

必要时可以拼接多个 reason，但首版建议保留主原因即可。

---

## 18. 统一接口

建议函数定义：

```python
def compute_allowed_cash_today(
    symbol_info: SymbolInfo,
    account_snapshot: AccountSnapshot,
    position: Position | None,
    recent_trade_stats: dict,
) -> tuple[float, str]:
    ...
```

返回：

```python
(allowed_cash_today, reason)
```

---

```python
def compute_final_trade_amount(
    allowed_cash_today: float,
    trend_decision: TrendDecision,
    symbol_info: SymbolInfo,
    account_snapshot: AccountSnapshot,
    position: Position | None,
    recent_trade_stats: dict,
) -> tuple[float, float, str]:
    ...
```

返回：

```python
(planned_amount_usd, final_amount_usd, reason)
```

---

## 19. 伪代码

```python
daily_base_budget = symbol.base_trade_amount_usd
weekly_total_budget = daily_base_budget * symbol.weekly_budget_multiplier

current_position_value = position.market_value if position else 0.0
remaining_position_capacity = max(0, symbol.max_position_usd - current_position_value)

used_weekly_budget = recent_trade_stats["buy_amount_5d"]
remaining_weekly_budget = max(0, weekly_total_budget - used_weekly_budget)

cash_limit = max(0, account_snapshot.cash_available)

allowed_cash_today = min(
    daily_base_budget,
    remaining_weekly_budget,
    remaining_position_capacity,
    cash_limit,
)

budget_multiplier = trend_decision.budget_multiplier
raw_planned_amount = allowed_cash_today * budget_multiplier

final_amount_usd = min(
    raw_planned_amount,
    remaining_weekly_budget,
    remaining_position_capacity,
    cash_limit,
)

if final_amount_usd < 50:
    final_amount_usd = 0
```

---

## 20. 示例

## 20.1 正常强趋势

```text
base_trade_amount_usd = 1000
weekly_budget_multiplier = 5
max_position_usd = 6000
cash_available = 10000
current_position_value = 2000
buy_amount_5d = 1000
trend_type = strong_uptrend
budget_multiplier = 1.5
```

计算：

```text
weekly_total_budget = 5000
remaining_weekly_budget = 4000
remaining_position_capacity = 4000
allowed_cash_today = min(1000, 4000, 4000, 10000) = 1000
raw_planned_amount = 1000 * 1.5 = 1500
final_amount_usd = min(1500, 4000, 4000, 10000) = 1500
```

结论：

```text
today can buy 1500
```

---

## 20.2 本周额度快用完

```text
buy_amount_5d = 4700
weekly_total_budget = 5000
```

则：

```text
remaining_weekly_budget = 300
allowed_cash_today = min(1000, 300, ..., ...) = 300
raw_planned_amount = 300 * 1.5 = 450
final_amount_usd = min(450, 300, ...) = 300
```

---

## 20.3 持仓上限已满

```text
max_position_usd = 5000
current_position_value = 5200
```

则：

```text
remaining_position_capacity = 0
allowed_cash_today = 0
final_amount_usd = 0
reason = "max_position_reached"
```

---

## 21. 日志要求

每次预算计算必须记录：

* ticker
* trade_date
* daily_base_budget
* weekly_total_budget
* used_weekly_budget
* remaining_weekly_budget
* current_position_value
* remaining_position_capacity
* cash_available
* trend_type
* budget_multiplier
* allowed_cash_today
* planned_amount_usd
* final_amount_usd
* reason

---

## 22. 首版明确不做的事情

本版本不实现：

* 根据波动率动态调预算
* 根据分位系统动态调预算
* 根据多标的组合总仓位动态压缩
* 根据宏观风险动态降杠杆
* 根据 unrealized pnl 自动减仓

首版只做：

```text
固定预算 + 趋势系数 + 上限裁剪
```

---

## 23. 当前版本的一个已知简化

本周预算首版近似使用：

```text
最近 5 日买入金额
```

而不是严格自然周。

原因：

* 更容易回测实现
* 与滚动预算思想更一致
* 后续可再升级为真实自然周 / 交易周

---

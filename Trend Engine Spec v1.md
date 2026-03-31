# 趋势模块规范（Trend Engine Spec v1）

## 1. 目标

将日线数据（OHLC）转换为：

* trend_type（趋势类型）
* trend_strength（趋势强度）
* buy_threshold_pct（买入阈值）
* rebound_pct（反弹确认）
* budget_multiplier（资金系数）

该模块输出必须 **无歧义、可复现、可回测一致**

---

## 2. 输入定义

输入数据（必须保证）：

* 至少 60 个交易日 OHLC
* 已按时间排序
* 无缺失

字段：

* close

---

## 3. MA 定义

使用 Simple Moving Average：

* MA5 = 最近5日收盘均值
* MA20 = 最近20日收盘均值
* MA60 = 最近60日收盘均值

说明：

* MA5 → 短期成本
* MA20 → 中期趋势
* MA60 → 大趋势 ([InCosmos Vision][1])

---

## 4. slope 定义（关键：必须统一）

采用**标准化斜率（避免价格尺度问题）**

```python
slope_n = (MA_n[today] - MA_n[today - k]) / MA_n[today - k]
```

参数：

* k = 3（固定，不允许随意修改）

输出：

* slope5
* slope20
* slope60

---

## 5. slope 状态编码

```text
> +  : slope > +0.002
> 0  : -0.002 <= slope <= 0.002
> -  : slope < -0.002
```

输出：

```python
slope_code = "s5,s20,s60"
例："+,+,+" / "+,0,-"
```

---

## 6. MA 排列编码

```text
case1: MA5 > MA20 > MA60
case2: MA20 > MA5 > MA60
case3: MA20 > MA60 > MA5
case4: MA60 > MA20 > MA5
case5: 其他（混乱）
```

输出：

```python
ma_order_code = "5>20>60"
```

---

## 7. 趋势分类（核心规则）

### 7.1 强上升趋势（strong_uptrend）

条件：

```text
MA5 > MA20 > MA60
AND slope5 > 0
AND slope20 > 0
AND slope60 > 0
```

---

### 7.2 弱上升趋势（weak_uptrend）

```text
MA5 > MA20 > MA60
AND slope20 > 0
AND slope60 >= 0
```

---

### 7.3 震荡（range）

```text
abs(MA5 - MA20)/MA20 < 0.01
AND abs(MA20 - MA60)/MA60 < 0.01
```

或：

```text
slope_code 包含多个 0
```

---

### 7.4 弱下降趋势（weak_downtrend）

```text
MA5 < MA20 < MA60
AND slope20 < 0
AND slope60 <= 0
```

---

### 7.5 强下降趋势（strong_downtrend）

```text
MA5 < MA20 < MA60
AND slope5 < 0
AND slope20 < 0
AND slope60 < 0
```

---

### 7.6 反弹结构（rebound_setup）

```text
MA20 > MA60
AND slope20 > 0
AND slope5 < 0
```

解释：

* 中期上涨
* 短期回调

👉 这是你系统的核心买点

---

## 8. 趋势强度（trend_strength）

定义：

```python
trend_strength = (
    abs(slope5) * 0.5 +
    abs(slope20) * 0.3 +
    abs(slope60) * 0.2
)
```

范围：

* 一般在 0 ~ 0.05

---

## 9. 买入阈值（buy_threshold_pct）

定义为：

```python
buy_threshold_pct = a * abs(slope20) + b
```

默认参数：

```python
a = 3.0
b = 0.01
```

解释：

* 趋势越强 → 回调要求越大
* 避免高位追涨

---

## 10. 反弹确认（rebound_pct）

```python
rebound_pct = buy_threshold_pct * 0.5
```

---

## 11. 资金系数（budget_multiplier）

映射表：

```python
strong_uptrend   → 1.5
weak_uptrend     → 1.2
range            → 0.8
weak_downtrend   → 0.5
strong_downtrend → 0.2
rebound_setup    → 1.3
```

---

## 12. 输出结构

```python
TrendDecision(
    trend_type=...,
    trend_strength=...,
    action_bias="buy_bias",
    buy_threshold_pct=...,
    rebound_pct=...,
    budget_multiplier=...,
    reason="MA5>MA20>MA60 & slopes positive"
)
```

---

## 13. 约束（必须遵守）

1. 所有参数必须固定写入 config
2. 不允许在代码中隐式调整阈值
3. 所有计算必须可回测复现
4. 所有输出必须写入日志

---

## 14. 当前版本限制

本版本：

* 不使用分位系统
* 不使用成交量
* 不使用波动率
* 不使用机器学习

仅基于：

👉 MA + slope

---

## 15. 下一步（明确）

下一阶段必须补充：

* 分位系统（pullback percentile）
* intraday 精确定义（极关键）

---

[1]: https://incosmos.vision/education/4072/?utm_source=chatgpt.com "基础指南｜技术指标参数设置的含义与实战优化"

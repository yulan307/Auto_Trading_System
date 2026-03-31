# Trend Engine

## 目标

将日线数据转换为稳定、可回测的趋势状态输出，为预算与日级信号提供统一输入。

## 输入

- 至少 60 个交易日的日线数据
- `close`
- MA 参数
- slope 参数

## 输出

- `TrendFeatures`
- `TrendDecision`

## 核心逻辑

### MA 定义

- `MA5`
- `MA20`
- `MA60`

### slope 定义

采用标准化斜率：

`slope_n = (MA_n[today] - MA_n[today-k]) / MA_n[today-k]`

首版固定：

- `k = 3`

### slope 状态编码

- `+`：`slope > 0.002`
- `0`：`-0.002 <= slope <= 0.002`
- `-`：`slope < -0.002`

### MA 排列编码

- `5>20>60`
- `20>5>60`
- `20>60>5`
- `60>20>5`
- 其他混乱状态

### 趋势分类

首版使用以下类型：

- `strong_uptrend`
- `weak_uptrend`
- `range`
- `weak_downtrend`
- `strong_downtrend`
- `rebound_setup`

### 趋势强度

`trend_strength = abs(slope5)*0.5 + abs(slope20)*0.3 + abs(slope60)*0.2`

### 阈值输出

- `buy_threshold_pct`
- `rebound_pct`
- `budget_multiplier`

## 状态变量

- MA 窗口
- slope lookback
- slope 阈值
- 趋势与预算映射表

## 边界条件

- 数据天数不足
- MA 基数为 0
- slope 无法计算
- 趋势不命中任何规则

## MVP范围

- 仅基于 MA + slope
- 不接入分位系统
- 不使用成交量、波动率、机器学习

## 测试方案

- MA 结果正确性
- slope 编码正确性
- `strong_uptrend` / `range` / `strong_downtrend` 覆盖

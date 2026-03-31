# Backtest Engine

## 目标

按历史交易日推进系统逻辑，并复用统一的数据、趋势、日内与执行模块。

## 输入

- `ticker`
- `start_date`
- `end_date`
- `runtime_context`

## 输出

- 回测结果摘要
- 交易记录
- 决策记录
- 指标结果

## 核心逻辑

- 逐日读取历史数据
- 计算趋势与日级信号
- 在需要时执行日内追踪
- 使用 mock broker 和虚拟账户推进状态
- 汇总绩效指标

## 主流程

1. 读取截至当日的历史日线数据
2. 计算 MA 特征
3. 分类趋势
4. 读取 symbol 配置
5. 读取账户快照与最近交易统计
6. 生成 `DailySignal`
7. 若 `action=buy`，读取当日 15 分钟数据并运行 `Intraday Engine`
8. 通过 `Mock Broker` 与 `Backtest Fill` 规则推进订单和成交
9. 记录 trade、order、decision、log
10. 进入下一交易日

## 状态变量

- 账户净值曲线
- 交易记录
- 决策记录

## 边界条件

- 数据缺失
- 当日无日内数据
- 订单状态异常
- 回测中断恢复

## MVP范围

- 单一 ticker
- 本地 SQLite
- 虚拟账户
- mock broker
- 统一复用正式模块接口

## 测试方案

- 单标的全流程跑通
- 交易记录生成
- 指标结果可输出
- 回测过程无异常中断

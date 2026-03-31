# Data Layer

## 目标

提供统一的数据获取、清洗、落盘与读取接口，屏蔽不同数据源差异，并保证后续回测与实盘复用相同数据结构。

## 输入

- `ticker`
- `interval`
- `start_date`
- `end_date`
- `source`

## 输出

- 标准化 OHLCV DataFrame
- SQLite 中的 `daily_bars` / `intraday_bars`

## 核心逻辑

### 数据获取

- 通过 provider 抽象统一调用 `yfinance`、`moomoo`、`ib`
- 首版只要求正式实现 `yfinance`

### 数据标准化

- 重命名字段
- 补全 `ticker` / `interval` / `source`
- 统一时间列为 `datetime`
- 去重、排序、检查数值合法性

### 本地持久化

- 使用 SQLite
- `daily.db` 存 `daily_bars`
- `intraday.db` 存 `intraday_bars`

### 更新流程

- provider 拉取数据
- 标准化
- 落盘
- 返回更新摘要

## 状态变量

- `daily.db`
- `intraday.db`
- `daily_bars`
- `intraday_bars`

## 边界条件

- provider 返回空数据
- 字段缺失
- 时间未排序
- 重复 bar
- `high/low` 不满足价格约束
- 时区不一致

## MVP范围

- `yfinance`
- 本地 SQLite
- `1d` 与 `15m` 两种 interval
- provider 抽象预留，`moomoo` / `ib` 暂不实现

## 正式接口

- `BaseDataProvider.fetch_bars(...)`
- `normalize_ohlcv_dataframe(...)`
- `save_bars(...)`
- `load_bars(...)`
- `update_symbol_data(...)`

## 测试方案

- 数据库初始化测试
- 读写一致性测试
- 标准化结果测试
- `SPY` 日线数据样例测试

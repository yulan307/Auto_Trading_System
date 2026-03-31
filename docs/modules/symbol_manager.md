# Symbol Manager

## 目标

维护可交易标的配置，并向趋势、预算、执行模块提供统一的标的参数。

## 输入

- `SymbolInfo`
- `symbol`
- `updates`
- `mode`

## 输出

- 单个 `SymbolInfo`
- 启用标的列表

## 核心逻辑

- 新增标的
- 查询标的
- 更新标的配置
- 按运行模式筛选启用标的

## 状态变量

- `symbols.db`
- `symbols` 表

## 边界条件

- `symbol` 重复
- `asset_type` 非法
- 基础金额或上限配置非法
- 某模式下没有启用标的

## MVP范围

- 单标的优先
- 本地 SQLite 存储
- 支持 `backtest` / `paper` / `live` 启用开关

## 测试方案

- 新增与查询测试
- 更新测试
- 启用标的筛选测试

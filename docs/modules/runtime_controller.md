# Runtime Controller

## 目标

统一加载配置、初始化上下文、创建日志系统，并根据运行模式注入数据、账户与执行依赖。

## 输入

- `config_path`

## 输出

- `runtime_context`

## 核心逻辑

- 读取 YAML 配置
- 合并默认值
- 解析项目内相对路径
- 初始化 logger
- 根据 `mode` 选择 provider / account / broker

## 状态变量

- `mode`
- `config`
- `logger`
- `daily_provider`
- `intraday_provider`
- `symbol_manager`
- `account_manager`
- `execution_engine`

## 边界条件

- 配置文件不存在
- YAML 根结构非法
- 运行模式非法
- 日志目录不可创建

## MVP范围

- `backtest` / `paper` / `live` 的配置入口
- 先完成配置与 logger 初始化
- 具体 provider / broker 注入后续逐阶段补全

## 测试方案

- 配置加载路径解析测试
- 非法配置报错测试
- runtime 返回结构测试

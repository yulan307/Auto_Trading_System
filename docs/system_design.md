# System Design

## 目标

本系统是一个以本地数据库为核心、可回测并可逐步迁移到 paper 和 live 的自动交易平台。

当前总目标来自根目录主规范：

- 数据获取与更新
- 标的管理
- 账户与资金管理
- 趋势判断
- 日内 15 分钟追踪
- 自动下单 / 撤单
- 完整日志体系
- 回测复用同一套模块
- 支持 `backtest` / `paper` / `live`

## 设计原则

### 单一职责

- Data Layer 只负责数据获取、清洗、存储与读取
- Symbol Manager 只负责标的配置
- Account Manager 只负责账户状态与交易记录
- Trend Engine 只负责趋势与预算相关计算
- Intraday Engine 只负责日内追踪与下单触发条件
- Execution Engine 只负责订单路由、撤单、成交状态
- Backtest Engine 只负责时间推进与结果汇总

### 模式统一

所有运行模式共享接口，只替换三类依赖：

- 数据源
- 账户源
- 执行源

### 本地优先

系统关键状态必须可以本地落盘，便于：

- 重启恢复
- 回测复盘
- 调试审计
- 日志追踪

### 可测试优先

所有模块必须支持独立测试，避免只能依赖全链路联调。

## 运行模式

### backtest

- 数据源：本地 `daily.db`、`intraday.db`
- 账户源：本地虚拟账户
- 执行源：mock broker

### paper

- 数据源：券商或本地缓存
- 账户源：本地虚拟账户或 paper account
- 执行源：mock broker

### live

- 数据源：券商实时数据与本地缓存辅助
- 账户源：真实券商账户
- 执行源：真实券商下单接口

## 模块边界

- [data_layer.md](modules/data_layer.md)
- [runtime_controller.md](modules/runtime_controller.md)
- [symbol_manager.md](modules/symbol_manager.md)
- [account_manager.md](modules/account_manager.md)
- [trend_engine.md](modules/trend_engine.md)
- [budget_engine.md](modules/budget_engine.md)
- [daily_signal.md](modules/daily_signal.md)
- [intraday_engine.md](modules/intraday_engine.md)
- [execution_engine.md](modules/execution_engine.md)
- [backtest_fill.md](modules/backtest_fill.md)
- [backtest_engine.md](modules/backtest_engine.md)
- [logging_system.md](modules/logging_system.md)

## 共享数据结构

当前核心共享对象包括：

- `OHLCVBar`
- `SymbolInfo`
- `AccountSnapshot`
- `Position`
- `TradeRecord`
- `OrderRequest`
- `OrderStatus`
- `TrendFeatures`
- `TrendDecision`
- `DailySignal`
- `IntradayState`
- `LogEvent`

字段定义以 `auto_trading_system_implementation_spec.md` 为主来源，并与代码保持一致。

## 开发顺序

当前正式开发顺序沿用主规范中的 7 个阶段：

1. 基础设施
2. 数据层
3. 标的与账户
4. 趋势引擎
5. 日内逻辑
6. 执行层
7. 回测引擎

## 文档治理规则

- 先更新 `docs/` 下正式文档，再调整代码
- 模块变更优先更新对应 `docs/modules/*.md`
- 研究性内容放入 `docs/research/`
- 根目录与 `backup/` 中的 Markdown 文件保留为历史来源，不作为正式维护入口

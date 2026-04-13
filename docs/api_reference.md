# API Reference

本文件是 `Auto_Trading_System` 的统一接口说明，目标是让协作者或其他 AI 在不通读代码的前提下，仍能理解系统结构、模块边界、主要 I/O 契约、状态落盘方式，以及新增设计时需要遵守的接口一致性。

本文档以当前 `app/` 与 `scripts/` 代码为事实来源，以 [system_design.md](system_design.md) 与 `docs/modules/*.md` 为设计意图来源。若二者不一致，以“当前代码可见接口”作为主描述对象，并在文末单列偏差/废弃项。

## 1. 系统总览

### 1.1 运行模式

| 模式 | 配置值 | 数据源定位 | 账户定位 | 执行定位 |
| --- | --- | --- | --- | --- |
| 回测 | `backtest` | 本地 SQLite，必要时可用 `yfinance` 补日线 | 本地虚拟账户 | `MockBroker` |
| 模拟盘 | `paper` | 设计目标已定义，脚本入口仍为占位 | 本地或 paper account | mock 或券商 paper 路由 |
| 实盘 | `live` | 设计目标已定义，脚本入口仍为占位 | 真实券商账户 | 券商下单接口 |

当前唯一跑通到脚本层的主链路是最小回测闭环：

`scripts/run_backtest.py -> runtime.init_runtime -> data 初始化 -> backtest.run_backtest -> account/logging 落盘 -> JSON 输出`

### 1.2 主入口

| 入口 | 角色 | 主要输出 |
| --- | --- | --- |
| `app/main.py` | 初始化运行时并打印摘要 | `mode`、`project_root`、`log_dir` |
| `scripts/init_db.py` | 初始化全部 SQLite 数据库 | 各数据库路径 JSON |
| `scripts/run_backtest.py` | 最小闭环回测入口 | 回测结果 JSON 文件 |
| `scripts/compute_trend_features.py` | 特征库批处理与 CSV 导出 | `feature.db` 更新与研究 CSV |
| `scripts/train_buy_sub_ml.py` | 交互式训练与发布买入强度模型 | 新实验产物目录与已发布模型目录 |
| `scripts/infer_buy_sub_ml.py` | 交互式选择模型并按 ticker 推理 | 每个 ticker 一个推理 CSV |
| `app/ml/__init__.py` | ML 汇总导出入口 | 暴露标签、训练、推理、发布接口 |

### 1.3 主数据流

1. `runtime.config_loader.load_config` 读取 YAML、合并默认值、解析绝对路径。
2. `runtime.controller.init_runtime` 组装 `RuntimeContext`，并创建 `AppLogger`。
3. `data.db.initialize_all_databases` 初始化 `daily/intraday/symbols/account/logs` 库。
4. `data.updater.update_daily_db` 或 `trend.features.update_feature_db` 维护日线与特征缓存。
5. `backtest.engine.run_backtest` 读取 `daily_bars`、生成信号、调用 mock broker、回写账户与日志。
6. `ml.*` 子系统在 `feature.db` 基础上派生 `buy_strength.db`、训练产物与推理 CSV。

## 2. 共享契约

### 2.1 配置结构

配置入口统一是 `runtime/config_loader.py:load_config(config_path)`。调用方只应依赖返回后的“解析完成配置”，不要绕过它自行拼路径。

| 一级键 | 关键子键 | 用途 |
| --- | --- | --- |
| `mode` | `backtest/paper/live` | 当前运行模式 |
| `timezone` | 时区字符串 | 默认交易时区 |
| `data` | `daily_provider` `intraday_provider` `daily_db_path` `feature_db_path` `intraday_db_path` `symbols_db_path` `account_db_path` `logs_db_path` | 数据与持久化路径 |
| `account` | `account_source` `initial_cash` | 账户来源与初始资金 |
| `execution` | `broker` `allow_fractional_default` | 下单路由与默认碎股策略 |
| `logging` | `log_level` `log_dir` | 日志级别与目录 |
| `strategy` | `ma_windows` `intraday_interval` `last_bar_force_trade` 及若干默认预算键 | 策略参数与默认交易参数 |
| `ml` | `enabled` `buy_model_version` `sell_model_version` | ML 子系统总开关与版本引用 |

`load_config` 的关键语义：

- 会将 `DEFAULT_CONFIG` 与 YAML 深度合并。
- 若配置文件位于 `config/` 目录下，`project_root` 会解析为仓库根目录。
- 所有 DB 路径和 `log_dir` 都会转成绝对路径。
- 缺少 `data/account/execution/logging/strategy/ml` 任一分段会直接抛错。

### 2.2 SQLite 介质与表

| 数据库 | 关键表 | 写入口 | 主要读入口 |
| --- | --- | --- | --- |
| `daily.db` | `daily_bars` `daily_coverage` | `save_bars`、`update_daily_db` | `load_bars` |
| `intraday.db` | `intraday_bars` | 当前只有表初始化，无正式维护脚本 | `load_bars` |
| `feature.db` | `trend_features_daily` | `trend.features.update_feature_db` | `trend.features.load_feature_rows` |
| `symbols.db` | `symbols` | `SymbolRepository.add_symbol/update_symbol` | `SymbolRepository.get_symbol` |
| `account.db` | `account_snapshots` `positions` `trade_records` `orders` | `AccountRepository`、`virtual_account.apply_filled_trade` | `AccountRepository` |
| `logs.db` | `log_events` | `loggingx.insert_log_event` / `AppLogger.log_event` | 直接 SQL 或后续分析脚本 |
| `buy_strength.db` | `buy_strength_daily` | `ml.buy_strength_label.update_buy_strength_db` | `load_strength_rows` |

### 2.3 共享数据对象

| 对象 | 来源 | 关键字段 | 用途 |
| --- | --- | --- | --- |
| `OHLCVBar` | `app.data.models` | `datetime` `ticker` `interval` `open/high/low/close` `volume` | 行情标准结构 |
| `SymbolInfo` | `app.symbols.models` | 市场、资产类型、模式开关、预算参数、碎股/force buy 开关 | 标的元数据与交易约束 |
| `AccountSnapshot` | `app.account.models` | `cash_available` `market_value` `total_asset` | 账户快照 |
| `Position` | `app.account.models` | `quantity` `avg_cost` `market_price` | 当前持仓 |
| `TradeRecord` | `app.account.models` | `trade_id` `order_id` `ticker` `side` `amount` | 成交记录 |
| `OrderRequest` | `app.execution.models` | `side` `order_type` `price` `amount_usd` `quantity` | 下单请求 |
| `OrderStatus` | `app.execution.models` | `status` `submitted_price` `filled_quantity` | 订单状态 |
| `TrendDecision` | `app.trend.models` | `trend_type` `action_bias` `buy_threshold_pct` `budget_multiplier` | 趋势层决策 |
| `DailySignal` | `app.trend.models` | `action` `target_price` `planned_amount_usd` `final_amount_usd` | 日级买入/持有信号 |
| `IntradayState` | `app.intraday.models` | `tracked_low/high` `order_active` `entered_trade` | 日内跟踪状态 |
| `LogEvent` | `app.loggingx.event_store` | `event_time` `module` `event_type` `payload_json` | 结构化日志持久化结构 |

### 2.4 常见返回值约定

- 数据更新类函数通常返回 `dict`，包含 `ticker`、时间范围、写入量、状态，例如 `update_daily_db`、`update_buy_strength_db`。
- 读取类函数优先返回：
  - dataclass 或 dataclass 列表，例如 `AccountRepository.get_position`
  - `list[dict]`，例如 `load_bars`
  - `pandas.DataFrame`，例如 `load_feature_rows`、`get_strength_pct_frame`
- 脚本主入口默认返回 `int` 作为退出码；真正的业务结果通过 JSON 文件或 stdout 输出。

## 3. 主系统模块

下面各节都按同一模板说明：职责边界、事实来源、公开入口、I/O、边界条件、模块对接。

### 3.1 `runtime`

**职责与边界**

- 负责配置加载、运行时上下文组装、日志初始化。
- 不负责业务计算，不负责数据更新，不负责订单执行。

**Source of truth**

- `app/runtime/config_loader.py`
- `app/runtime/context.py`
- `app/runtime/controller.py`

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `load_config(config_path)` | YAML 路径 | 解析后的配置字典 | 深度合并默认值，解析绝对路径并校验 |
| `init_runtime(config_path)` | YAML 路径 | `dict` 形式运行时上下文 | 创建 logger，挂载 `mode/config/ml/metadata` |
| `RuntimeContext.to_dict()` | dataclass 实例 | `dict[str, Any]` | 为脚本层提供松耦合上下文字典 |

**使用边界**

- 所有脚本都应先走 `load_config` 或 `init_runtime`，不要直接读 YAML。
- `RuntimeContext` 目前是轻量容器，不做懒加载，也不自动实例化 provider/broker/symbol manager。
- `init_runtime` 会立刻写一条 `system_init` 日志到 `logs.db` 与日志文件。

**对接关系**

- 下游：所有脚本入口、`app/main.py`、回测流程。
- 上游：无，上层直接调用。

### 3.2 `data`

**职责与边界**

- 负责 SQLite 初始化、OHLCV 规范化、原始行情读写、日线覆盖率缓存维护。
- 不负责趋势决策，也不负责账户与交易语义。

**Source of truth**

- `app/data/db.py`
- `app/data/repository.py`
- `app/data/schema.py`
- `app/data/updater.py`
- `app/data/providers/*.py`

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `connect_sqlite(db_path)` | DB 路径 | `sqlite3.Connection` | 自动创建父目录，启用 `Row` 与外键 |
| `initialize_all_databases(config)` | 配置字典 | 路径字典 | 初始化全部基础数据库 |
| `normalize_ohlcv_dataframe(bars, ..., ticker, interval, source)` | provider 输出 | `list[dict]` | 统一列名、校验高低价、去重排序 |
| `save_bars(db_path, table_name, bars)` | 标准化 bar 列表 | 写入条数 `int` | UPSERT 到 `daily_bars`/`intraday_bars` |
| `load_bars(...)` | ticker、interval、时间范围 | `list[dict]` | 读原始 bar，按 `datetime ASC` 返回 |
| `update_symbol_data(...)` | provider、ticker、区间 | 结果字典 | 一次性抓取并写入指定表 |
| `update_daily_db(...)` | ticker、日期区间 | 结果字典 | 带 `daily_coverage` 的增量更新入口 |

**关键逻辑**

- `update_daily_db` 是当前唯一受支持的 `daily.db` 维护入口。
- 它会先把已有 bar 反种子到 `daily_coverage`，避免重复检查。
- 周末会直接写 `checked_missing`，工作日缺口会按连续日期段批量向 provider 拉取。
- provider 规范接口是 `fetch_bars(ticker, interval, start_date, end_date)`；当前真实可用实现是 `YFinanceProvider`。

**使用边界**

- `update_daily_db` 目前只支持 `interval='1d'`，传入 `15m` 会直接报错。
- `load_bars` 与 `save_bars` 假设调用方已知表名；表选择逻辑不自动外推。
- `normalize_ohlcv_dataframe` 接收 list 或 dataframe-like 对象，但要求至少含 `datetime/open/high/low/close/volume`。

**对接关系**

- 上游：`scripts/init_db.py`、`scripts/run_backtest.py`、`trend.features.update_feature_db`
- 下游：`trend.features`、`backtest.engine`

### 3.3 `symbols`

**职责与边界**

- 负责标的元数据定义与持久化。
- 不负责市场数据抓取，不负责订单状态。

**Source of truth**

- `app/symbols/models.py`
- `app/symbols/repository.py`
- `app/symbols/manager.py`

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `SymbolInfo(...)` | 标的基础信息、预算约束 | dataclass | 写入前的强约束对象 |
| `SymbolRepository.add_symbol(symbol_info)` | `SymbolInfo` | `None` | 插入一条 symbol 记录 |
| `SymbolRepository.get_symbol(symbol)` | ticker | `SymbolInfo | None` | 读取并反序列化 `tags` 与布尔位 |
| `SymbolRepository.update_symbol(symbol, updates)` | 局部更新字典 | `None` | 动态生成 SQL 更新语句 |
| `SymbolManager.list_enabled_symbols(mode)` | 模式名 | `list[SymbolInfo]` | 扫描并按模式过滤已启用标的 |

**使用边界**

- `asset_type` 只允许 `stock` 或 `etf`。
- `max_position_usd` 不得小于 `base_trade_amount_usd`。
- `weekly_budget_multiplier` 若给出必须大于等于 1。
- `list_enabled_symbols` 当前采用“全表扫描再过滤”，适合少量标的，不应视为大规模筛选接口。

**对接关系**

- 上游：未来配置工具、回测中的默认 symbol fallback。
- 下游：`trend.budget`、`backtest.engine`。

### 3.4 `account`

**职责与边界**

- 负责账户快照、持仓、成交记录的存取与虚拟账户更新。
- 不直接管理订单生命周期，也不负责行情估值刷新。

**Source of truth**

- `app/account/models.py`
- `app/account/repository.py`
- `app/account/virtual_account.py`
- `app/account/manager.py`

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `AccountRepository.get_account_snapshot()` | 无 | `AccountSnapshot | None` | 取最新快照 |
| `AccountRepository.save_account_snapshot(snapshot)` | 快照对象 | `None` | 追加写入快照表 |
| `AccountRepository.get_position(ticker)` | ticker | `Position | None` | 读取当前持仓 |
| `AccountRepository.upsert_position(position)` | 持仓对象 | `None` | 覆盖写当前持仓 |
| `AccountRepository.apply_trade(trade_record)` | 成交对象 | `None` | 仅写 `trade_records` 表 |
| `AccountRepository.get_recent_trade_stats(ticker, as_of_date)` | ticker、日期 | `dict` | 统计近 5 日与本周买入金额 |
| `reset_virtual_account(initial_cash, repository, mode)` | 初始资金、仓储 | `None` | 初始化虚拟账户 |
| `apply_filled_trade(trade_record, repository)` | 成交对象 | `None` | 更新持仓与账户快照，再记账成交 |

**关键逻辑**

- `apply_filled_trade` 才是真正的“虚拟成交结算入口”。
- 买入会降低现金、增加 `market_value`，同时按加权成本重算 `avg_cost`。
- 卖出路径做了数量校验，但当前主回测只实现买入，不会清空持仓记录。

**使用边界**

- 若账户未初始化，`apply_filled_trade` 会报 `virtual account is not initialized`。
- 当前仓位表只存“当前状态”，没有仓位历史表。
- `orders` 表已建表，但账户模块当前并不维护它。

**对接关系**

- 上游：`backtest.engine`、未来 live/paper 执行结算。
- 下游：`trend.budget` 消费账户与持仓快照。

### 3.5 `trend`

**职责与边界**

- 当前已稳定的是“特征存储层”和“预算/日级信号层”。
- 历史上的 MA 分类链路已在设计上废弃，但回测实现尚未完全迁移。

**Source of truth**

- `app/trend/features.py`
- `app/trend/budget.py`
- `app/trend/models.py`
- `app/trend/signal.py`
- `docs/modules/trend_engine.md`
- `docs/modules/trend_feature_store.md`

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `compute_allowed_cash_today(symbol, account, position, recent_trade_stats, decision)` | 标的、账户、仓位、交易统计、趋势决策 | 预算结果字典 | 计算可用资金、计划金额、最终金额 |
| `generate_daily_signal(...)` | 日线 OHLC、趋势决策、账户上下文 | `DailySignal` | 生成 `buy` 或 `hold` |
| `update_feature_db(...)` | ticker、日期区间 | `bool` | 日线与特征缓存联合维护入口 |
| `load_feature_rows(...)` | ticker、日期区间 | `DataFrame` | 读取 `trend_features_daily` |
| `run_trend_feature_pipeline(...)` | 多 ticker、输出目录 | `TrendFeatureRunResult` | 批量更新 `feature.db` 并导出 CSV |

**关键逻辑**

- 特征层是当前趋势分析的 source of truth。
- `update_feature_db` 会先触发 `update_daily_db`，然后只重算缺失区间和少量左边界回填窗口。
- `compute_allowed_cash_today` 综合日预算、周预算、单标的上限、现金上限，最终对小于 `50 USD` 的交易归零。
- `generate_daily_signal` 只有在 `action_bias == buy_bias`、阈值存在且预算大于 0 时才会发出 `buy`。

**使用边界**

- 新的策略研究与 ML 特征消费应优先依赖 `feature.db` 的 `hist_*` 列，而不是旧 MA 分类接口。
- `TrendDecision` 目前是上游输入对象，实际生产者在当前代码中缺失；回测仍引用已移除的 `classify_trend`。
- `generate_daily_signal` 本身不做成交，只给出目标价与预算结果。

**对接关系**

- 上游：`data.updater`
- 下游：`ml.buy_strength_label`、`ml.buy_sub_ml`、回测策略层、未来日内决策

### 3.6 `intraday`

**职责与边界**

- 负责“已有日级买入意图之后”的日内跟踪状态与反弹触发判断。
- 当前未接入主闭环，仅提供纯函数/轻量状态对象。

**Source of truth**

- `app/intraday/models.py`
- `app/intraday/tracker.py`
- `app/intraday/signal.py`

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `init_intraday_state(...)` | ticker、trade_date、是否允许强制买入 | `IntradayState` | 初始化状态对象 |
| `update_buy_tracking_state(state, bar, has_active_order=False)` | 状态与单根 15m bar | 更新后的 `IntradayState` | 维护 `tracked_low/high` 与最后 bar 时间 |
| `build_intraday_signal(state, bar, daily_signal, rebound_pct)` | 状态、bar、日级信号、反弹阈值 | `dict` | 返回 `hold` 或 `place_limit_buy` |

**使用边界**

- 该模块假设调用方已先得到 `DailySignal`。
- `build_intraday_signal` 当前返回普通字典，不是 dataclass。
- 未实现撤单、force buy 执行和多订单管理；`current_order_id/order_active` 等字段尚未形成完整状态机。

**对接关系**

- 上游：`trend.generate_daily_signal`
- 下游：未来 `execution` 层

### 3.7 `execution`

**职责与边界**

- 负责订单提交、撤单、状态查询的抽象。
- 当前只有 mock broker 具备最小行为；真实 broker 类仍是空骨架。

**Source of truth**

- `app/execution/models.py`
- `app/execution/router.py`
- `app/execution/mock_broker.py`
- `app/execution/ib_broker.py`
- `app/execution/moomoo_broker.py`

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `OrderRequest(...)` | side、order_type、price、amount、quantity | dataclass | 下单请求结构 |
| `OrderStatus(...)` | 订单字段 | dataclass | 订单状态结构 |
| `ExecutionEngine.submit_order(order_request)` | 请求对象 | broker 返回值 | 薄封装到 broker |
| `ExecutionEngine.cancel_order(order_id)` | 订单号 | broker 返回值 | 薄封装到 broker |
| `ExecutionEngine.get_order_status(order_id)` | 订单号 | broker 返回值 | 薄封装到 broker |
| `MockBroker.place_order(order_request)` | 请求对象 | `OrderStatus` | 生成 `submitted` 状态 |

**使用边界**

- `MockBroker.place_order` 不会自动成交，只会返回 `submitted`。
- `limit` 单必须提供 `price`，`amount_usd` 必须大于 0。
- `ExecutionEngine` 不做审计、不落盘、不记录订单表。

**对接关系**

- 上游：回测与未来日内策略层。
- 下游：mock broker 或未来券商实现。

### 3.8 `backtest`

**职责与边界**

- 负责最小闭环回测主循环、时间推进、调用策略与虚拟账户更新。
- 当前不是一个通用回测框架，更像“为最小闭环验证服务的特定 orchestrator”。

**Source of truth**

- `app/backtest/engine.py`
- `scripts/run_backtest.py`
- `docs/modules/minimal_closed_loop.md`

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `run_backtest(ticker, start_date, end_date, runtime_context)` | ticker、区间、运行时 | 结果字典 | 主回测入口 |
| `scripts.run_backtest._ensure_daily_data_ready(...)` | 配置、ticker、区间 | 结果字典 | 确保回测区间日线数据可用 |
| `backtest.metrics.compute_metrics(*args, **kwargs)` | 任意 | 占位 | 尚未实现 |
| `backtest.report.build_report(*args, **kwargs)` | 任意 | 占位 | 尚未实现 |
| `backtest.runner.run()` | 无 | 占位 | 尚未实现 |

**关键逻辑**

- 初始化时若账户无快照，会调用 `reset_virtual_account`。
- 若 `symbols.db` 没有该 ticker，会根据配置构造一个默认 `SymbolInfo`。
- 当前成交规则是“若 `daily_signal.action == buy` 且 `low <= target_price`，则以 `target_price` 视为当日成交”。
- 成交后调用 `MockBroker.place_order` 生成订单号，再用 `apply_filled_trade` 更新虚拟账户。

**使用边界**

- 当前回测仅支持买入，不支持卖出、手续费、滑点、停牌、15m 回放成交。
- 若可用 bar 少于 `63` 根，会返回 `status=insufficient_data`。
- 当前文件仍引用已移除的 `trend.classifier` 与 `compute_ma_features`，这使其在现状代码下无法通过导入测试，见文末偏差表。

**对接关系**

- 上游：`scripts/run_backtest.py`
- 下游：`account`、`execution`、`loggingx`、历史上依赖的趋势决策接口

### 3.9 `loggingx`

**职责与边界**

- 负责结构化日志格式化、文件分流与日志事件落盘。
- 不负责业务告警路由，不负责日志分析。

**Source of truth**

- `app/loggingx/event_store.py`
- `app/loggingx/logger.py`

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `setup_logging(config)` | 配置字典 | `AppLogger` | 初始化 console/app/trade/decision/error handler |
| `AppLogger.log_event(...)` | level、module、event_type、message、payload | `None` | 同时写文件与 `logs.db` |
| `AppLogger.shutdown()` | 无 | `None` | 关闭并移除 handler |
| `insert_log_event(...)` | 结构化字段 | `None` | 直接写入 `log_events` |

**使用边界**

- `level` 必须是 Python logging 支持的级别。
- 结构化 payload 会被 JSON 序列化到文件与 `payload_json` 字段。
- `setup_logging` 每次都会清理同名 logger 上已有 handler，避免重复输出。

**对接关系**

- 上游：`runtime.init_runtime`
- 下游：所有业务模块都可写事件；当前实际主要由 `runtime`、`backtest` 使用

## 4. ML 子系统

ML 子系统当前是“建立在交易主链路数据缓存之上的独立研究/建模子系统”。它直接依赖 `trend.features`，但尚未反向接入主交易决策。

### 4.1 `ml.common`

**职责与边界**

- 统一 ML 子系统的默认路径、常量与输入规整工具。
- 不直接产生标签、模型或推理结果。

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `DEFAULT_FEATURE_DB_PATH` 等常量 | 无 | `Path` | 默认 feature/label/model/output 路径 |
| `normalize_tickers(tickers)` | str 或序列 | `list[str]` | 统一 ticker 格式 |
| `coerce_date_str(value, default_today=False)` | 日期值 | `YYYY-MM-DD` | 统一日期字符串 |
| `normalize_buy_model_version(model_version)` | 版本字符串 | `(registry_value, version_name)` | 统一 registry 与目录名 |
| `validate_sqlite_identifier(identifier)` | 标识符 | 同字符串 | 用于防止无效表名 |

**边界**

- ML 模块内部应尽量复用这些工具，避免自行约定路径和版本格式。

### 4.2 `ml.buy_strength_label`

**职责与边界**

- 从 `feature.db` 的日级特征派生“买入强度标签”，并维护 `buy_strength.db`。
- 输出是监督学习标签，不是交易指令。

**Source of truth**

- `app/ml/buy_strength_label/*.py`

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `init_buy_strength_db(db_path, table_name)` | DB 路径 | `None` | 初始化标签库 |
| `update_buy_strength_db(ticker, start_date, end_date, ...)` | ticker、区间 | 结果字典 | 维护标签缓存 |
| `load_strength_rows(...)` | ticker、区间 | `DataFrame` | 读取原始强度标签 |
| `get_strength_pct_frame(...)` | tickers、结束日期、月数 | `DataFrame` | 生成滚动百分位标签 |
| `compute_raw_strength_from_feature_df(feature_df)` | 特征表 | `DataFrame` | 从特征列计算基础强度 |

**关键逻辑**

- `update_buy_strength_db` 会先调用 `trend.features.update_feature_db` 确保特征齐全。
- 它只对尚不存在的日期生成标签，已有日期视为缓存。
- `get_strength_pct_frame` 会在目标窗口外额外回读两年数据，用于计算当前值在历史分布中的百分位。

**使用边界**

- `strength_pct_length_month` 必须大于 0。
- 输出 DataFrame 的核心列是 `ticker/date/strength/label_version/strength_pct`。

**对接关系**

- 上游：`trend.features`
- 下游：`ml.buy_sub_ml`

### 4.3 `ml.buy_sub_ml`

**职责与边界**

- 负责买入强度预测模型的数据集构建、训练实验、离线推理与版本发布。
- 当前是研究/实验能力，不是运行时线上服务。

**Source of truth**

- `app/ml/buy_sub_ml/*.py`

**公开入口**

| 接口 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `build_buy_sub_ml_dataset(...)` | tickers、结束日期、标签窗口 | `DataFrame` | 生成 `ticker/date/strength/hist_*/strength_pct` 数据集 |
| `fit_strength_model(train_df, ...)` | `hist_* + strength_pct` DataFrame | `(model_params, train_logs)` | 全样本拟合低层入口 |
| `predict_strength_pct(hist_df, model_params)` | `hist_*` DataFrame、模型参数 | `np.ndarray` | 严格按训练时特征顺序推理 |
| `run_buy_sub_ml_experiment(...)` | tickers、结束日期、版本、训练配置 | 结果字典 | 训练并落盘实验产物 |
| `infer_buy_strength_pct(...)` | tickers、起止日期、模型版本 | CSV 路径字符串 | 用已发布模型做离线推理 |
| `promote_buy_model(artifact_dir, model_version, ...)` | 实验产物目录、版本号 | 结果字典 | 复制产物并更新 registry |
| `train_buy_sub_ml_model(...)` | 数据集、特征列、配置 | 训练结果字典 | 低层训练入口 |

**关键逻辑**

- 标签来源固定是 `ml.buy_strength_label.get_strength_pct_frame`，其输出中的 `strength` 与 `strength_pct` 是唯一标签口径。
- 特征来源固定是 `trend.features.load_feature_rows`，训练与推理都只消费 `hist_*` 数值列，不使用 `ticker/datetime/fut_*/score/raw_strength/regime`。
- `fit_strength_model` 使用全样本拟合，不再做 train/valid/test 切分；默认模型是 `MLP([64, 32]) + Sigmoid`，损失是带 `strength_pct` 权重的 MSE。
- 训练时会按列名字典序锁定 `feature_columns`，并把 `StandardScaler` 的 `mean/scale`、模型权重、训练超参数和 full-fit 指标打包到 `model_params`。
- 实验训练会生成模型、scaler、特征列、训练配置、指标、预测样本，并保存到 `outputs/tmp/buy_sub_ml/...`。
- 版本发布会将实验产物复制到 `models/buy/<version_name>/`，并更新 `models/buy/registry.json` 的 `active_version`。
- 推理结果输出是 CSV，而不是数据库写回；CSV 会保留 `ticker/date`、训练所需 `feature_columns`、`strength`、`strength_pct`、`pred_strength_pct` 与 `model_version`。

**使用边界**

- `infer_buy_strength_pct` 若找不到模型目录、没有可用特征、或缺少产物文件会直接报错。
- `predict_strength_pct` 会对缺列、非数值列、以及必需特征上的缺失值直接报错；上层 `infer_buy_strength_pct` 只会对本次实际推理样本做 `dropna` 筛掉不完整行。
- `train_buy_sub_ml_model` 当前是兼容型包装器，内部仍会走 `fit_strength_model` 的全样本训练口径。
- 当前主交易链路没有消费这些预测值，接入交易前需要额外定义线上契约。

**对接关系**

- 上游：`ml.buy_strength_label`、`trend.features`
- 下游：模型仓库 `models/buy`、推理 CSV、未来研究/策略模块

## 5. 脚本入口

| 脚本 | 当前状态 | 依赖模块 | 输出物/副作用 |
| --- | --- | --- | --- |
| `scripts/init_db.py` | 可用 | `runtime.config_loader` `data.db` | 初始化所有 SQLite 库 |
| `scripts/run_backtest.py` | 可用但受回测漂移影响 | `runtime` `data` `backtest` | 回测 JSON、日志、账户记录 |
| `scripts/compute_trend_features.py` | 可用 | `trend.features` | 更新 `feature.db` 并导出研究 CSV |
| `scripts/train_buy_sub_ml.py` | 可用 | `ml.buy_sub_ml` `models/buy` | 交互式训练、实验落盘、模型发布 |
| `scripts/infer_buy_sub_ml.py` | 可用 | `ml.buy_sub_ml` `models/buy` | 交互式选模并按 ticker 输出推理 CSV |
| `scripts/update_daily_data.py` | 占位 | 无正式实现 | 抛 `NotImplementedError` |
| `scripts/update_intraday_data.py` | 占位 | 无正式实现 | 抛 `NotImplementedError` |
| `scripts/add_symbol.py` | 占位 | 无正式实现 | 抛 `NotImplementedError` |
| `scripts/run_paper.py` | 占位 | 无正式实现 | 抛 `NotImplementedError` |
| `scripts/run_live.py` | 占位 | 无正式实现 | 抛 `NotImplementedError` |

建议把脚本视为“面向操作流程的编排层”，不要把业务规则写回脚本；新增能力时优先补 `app/` 模块，再决定是否加脚本入口。

## 6. 模块对接关系

### 6.1 交易主链路

1. `runtime` 提供配置与日志。
2. `data` 提供 `daily_bars` 与 `intraday_bars`。
3. `symbols` 提供单标的预算与模式开关。
4. `trend` 基于账户、持仓和特征给出日级信号。
5. `intraday` 基于日级信号做日内确认。
6. `execution` 路由订单到 mock 或真实 broker。
7. `account` 根据成交结果回写账户与持仓。
8. `loggingx` 对关键事件做双写日志。
9. `backtest` 是目前唯一把上述链路串起来的 orchestrator。

### 6.2 研究与 ML 链路

1. `data.update_daily_db` 维护 `daily.db`。
2. `trend.update_feature_db` 在 `feature.db` 中生成 `hist_*` / `fut_*` 特征。
3. `buy_strength_label.update_buy_strength_db` 从特征生成标签并写 `buy_strength.db`。
4. `buy_sub_ml.build_buy_sub_ml_dataset` 合并标签与 `hist_*` 特征。
5. `buy_sub_ml.run_buy_sub_ml_experiment` 训练实验并输出产物。
6. `buy_sub_ml.promote_buy_model` 发布实验版本。
7. `buy_sub_ml.infer_buy_strength_pct` 读取已发布版本并输出预测 CSV。

### 6.3 依赖矩阵

| 模块 | 主要消费 | 主要产出 |
| --- | --- | --- |
| `runtime` | YAML 配置 | 运行时上下文、logger |
| `data` | provider 原始数据 | `daily.db`/`intraday.db` |
| `symbols` | 标的配置输入 | `symbols.db`、`SymbolInfo` |
| `account` | 成交事件 | `account.db` 中快照/持仓/成交 |
| `trend` | `daily.db`、账户、标的信息 | `feature.db`、预算结果、`DailySignal` |
| `intraday` | `DailySignal`、15m bar | 日内触发字典、`IntradayState` |
| `execution` | `OrderRequest` | `OrderStatus` |
| `backtest` | 日线、symbol、account、trend、execution | 回测结果字典、日志、账户更新 |
| `loggingx` | 任意业务事件 | 文件日志、`logs.db` |
| `ml.buy_strength_label` | `feature.db` | `buy_strength.db`、百分位标签 DataFrame |
| `ml.buy_sub_ml` | 特征与标签缓存 | 模型产物、registry、推理 CSV |

## 7. 使用边界与设计约束

- 若新增模块需要共享状态，优先落盘到现有 SQLite 体系，并在本文件补充表与写入口。
- 若新增策略逻辑依赖趋势特征，应优先通过 `trend.features.load_feature_rows` 读取缓存，而不是在策略模块里重复计算。
- 若新增 broker/account 实现，应保持 `ExecutionEngine` 和 `BaseAccountManager` 的当前接口形状，避免脚本层被迫知道具体券商实现。
- 若新增 ML 能力直接参与交易决策，必须先定义“模型输出如何转成 `TrendDecision` 或 `DailySignal`”的稳定契约；当前仓库尚无这层接口。
- 任何新脚本都应把业务逻辑放在 `app/` 下的可复用函数中，脚本只做参数解析、初始化和结果导出。

## 8. 偏差、废弃项与当前风险

| 项目 | 当前状态 | 影响 |
| --- | --- | --- |
| `app.backtest.engine` 仍引用 `app.trend.classifier.classify_trend` 与 `app.trend.features.compute_ma_features` | 代码中存在，实际模块已移除 | 导致导入失败，`pytest` 在 `tests/test_backtest_minimal_loop.py` 收集阶段报错 |
| `docs/modules/trend_engine.md` 已声明旧 MA 分类链路废弃 | 设计文档已更新 | 回测实现与测试尚未迁移到新的 feature-store 决策链路 |
| `backtest.metrics.py` `backtest.report.py` `backtest.runner.py` | 仍是占位函数 | 不应被视为稳定 API |
| `scripts/update_daily_data.py` `update_intraday_data.py` `add_symbol.py` `run_paper.py` `run_live.py` | 均直接抛 `NotImplementedError` | 文档可引用其意图，但不能当成可执行入口 |
| `account.db` 中的 `orders` 表 | 已建表但无仓储维护逻辑 | 当前订单状态不持久化 |
| `intraday` 状态机字段比实际逻辑更丰富 | 数据结构存在，但流程未闭环 | 新设计接入前需要先补完整订单/撤单状态机 |

## 9. 推荐阅读顺序

1. 先读本文档第 1、2、6 节，建立系统全貌。
2. 若关心交易主链路，再读第 3 节中的 `runtime/data/symbols/account/trend/backtest`。
3. 若关心研究与建模，再读第 4 节和 [modules/trend_feature_store.md](modules/trend_feature_store.md)。
4. 若准备改动具体模块，再回看对应 `docs/modules/*.md` 以对齐原始设计意图。

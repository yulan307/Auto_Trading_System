# 自动交易平台系统开发文档（模块细化版）

## 设计目标
本文件用于指导 Codex 自动生成代码，所有模块均定义：
- 输入（Input）
- 输出（Output）
- 核心逻辑（Logic）
- 关键约束（Constraints）

---

# 0. 运行控制模块（Runtime Controller）

## 接口
### init_runtime(config)
输入：
- config: dict（运行模式、数据源、账户源）

输出：
- runtime_context: dict

逻辑：
- 判断模式（backtest / paper / live）
- 初始化数据源连接
- 初始化账户源
- 初始化日志

---

# 1. 数据层（Data Layer）

## 1.1 fetch_data()
输入：
- ticker: str
- interval: str ("1d", "15m")
- start_date: datetime
- end_date: datetime
- source: str ("yfinance", "moomoo", "ib")

输出：
DataFrame：
- datetime, open, high, low, close, volume

逻辑：
- 调用不同 provider
- 统一字段
- 清洗缺失值
- 标准化时区

约束：
- datetime 必须排序
- 不允许重复数据

---

## 1.2 save_to_db()
输入：
- dataframe
- table_name

输出：
- None

逻辑：
- 写入 sqlite
- 去重

---

## 1.3 load_from_db()
输入：
- ticker
- interval

输出：
- DataFrame

---

# 2. 标的管理模块（Symbol Manager）

## 2.1 add_symbol(symbol_info)
输入：
- SymbolInfo

输出：
- success: bool

---

## 2.2 get_symbol(symbol)
输出：
- SymbolInfo

---

## 2.3 update_symbol(symbol, fields)
输出：
- success

---

# 3. 资金管理模块（Capital Manager）

## 3.1 get_account_status(ticker)
输出：
- cash_available
- position_size
- last_5d_trade_count
- last_5d_volume
- weekly_trade_count
- weekly_volume

---

## 3.2 virtual_account_update(order)
输入：
- order

逻辑：
- 更新持仓
- 更新现金
- 写入交易记录

---

# 4. 趋势模块（Trend Engine）

## 4.1 compute_ma_features(data)
输出：
- ma5, ma20, ma60
- slope5, slope20, slope60

---

## 4.2 classify_trend(features)
输出：
- trend_type
- strength

---

## 4.3 compute_budget(symbol, account)
输出：
- allowed_cash_today

---

## 4.4 compute_trade_amount(trend, budget)
输出：
- trade_amount

---

# 5. 决策模块（Decision Engine）

## 5.1 generate_signal()
输入：
- trend
- account
- symbol_config

输出：
- action ("buy", "sell", "hold")
- target_price
- amount

---

# 6. 日内策略模块（Intraday Engine）

## 6.1 track_low()
输入：
- 15m data stream

输出：
- current_low
- rebound_detected

---

## 6.2 place_order_condition()
条件：
- rebound + below threshold

---

## 6.3 cancel_order_condition()
条件：
- new lower low

---

## 6.4 force_trade_last_bar()
条件：
- last 15 min
- 未成交

---

# 7. 下单模块（Execution Engine）

## 7.1 place_order()
输入：
- ticker
- price
- amount

输出：
- order_id

---

## 7.2 cancel_order(order_id)

---

## 7.3 mock_execution()
逻辑：
- 即时成交
- 更新账户

---

# 8. 日志模块（Logging）

## log_event(level, message, context)

---

# 9. 回测引擎（Backtest Engine）

## run_backtest()
逻辑：
- 遍历历史数据
- 调用决策模块
- 调用虚拟账户
- 记录结果

输出：
- pnl
- trades
- metrics

---

# 10. 扩展接口

- 卖出策略（sell_engine）
- 黑天鹅处理（risk_engine）
- 分位系统（pullback_engine）
- 多标的组合（portfolio_engine）

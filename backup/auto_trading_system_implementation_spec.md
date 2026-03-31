# 自动交易平台系统开发文档（可直接用于 Codex 实现）

## 1. 文档目标

本文件不是说明性笔记，而是**可直接驱动代码实现**的开发规范。
目标是让 Codex / 开发代理基于本文件，逐步生成一个具备以下能力的自动交易系统：

- 数据获取与更新
- 标的管理
- 账户与资金管理
- 趋势判断
- 日内 15min 追踪
- 自动下单 / 撤单
- 完整日志体系
- 回测引擎复用同一套模块
- 支持 backtest / paper / live 三种运行模式

---

## 2. 总体设计原则

### 2.1 单一职责
每个模块只负责一件事：
- Data Layer 只负责数据获取 / 清洗 / 存储
- Symbol Manager 只负责标的配置
- Account Manager 只负责账户读取与更新
- Trend Engine 只负责趋势与交易金额计算
- Intraday Engine 只负责日内追踪逻辑
- Execution Engine 只负责下单 / 撤单 / 成交回报
- Backtest Engine 只负责按时间推进并复用上述模块

### 2.2 模式统一
所有模式共享同一套接口：
- `backtest`
- `paper`
- `live`

不同模式之间，只替换：
- 数据源
- 账户源
- 执行源

### 2.3 本地优先
系统核心状态必须可以本地落盘，便于：
- 重启恢复
- 回测复盘
- 调试审计
- 日志追踪

### 2.4 可测试优先
所有模块都必须允许独立测试，避免“只有全系统联调才能运行”。

---

# 3. 目录结构规范

```text
auto_trading_system/
├─ README.md
├─ requirements.txt
├─ config/
│  ├─ config.example.yaml
│  ├─ backtest.yaml
│  ├─ paper.yaml
│  └─ live.yaml
├─ data/
│  ├─ raw/
│  ├─ processed/
│  ├─ daily.db
│  ├─ intraday.db
│  ├─ symbols.db
│  ├─ account.db
│  └─ logs.db
├─ logs/
│  ├─ app.log
│  ├─ trade.log
│  ├─ decision.log
│  └─ error.log
├─ app/
│  ├─ main.py
│  ├─ runtime/
│  │  ├─ controller.py
│  │  ├─ config_loader.py
│  │  └─ context.py
│  ├─ data/
│  │  ├─ models.py
│  │  ├─ schema.py
│  │  ├─ db.py
│  │  ├─ repository.py
│  │  ├─ updater.py
│  │  └─ providers/
│  │     ├─ base.py
│  │     ├─ yfinance_provider.py
│  │     ├─ moomoo_provider.py
│  │     └─ ib_provider.py
│  ├─ symbols/
│  │  ├─ models.py
│  │  ├─ manager.py
│  │  └─ repository.py
│  ├─ account/
│  │  ├─ models.py
│  │  ├─ manager.py
│  │  ├─ repository.py
│  │  ├─ virtual_account.py
│  │  ├─ moomoo_account.py
│  │  └─ ib_account.py
│  ├─ trend/
│  │  ├─ features.py
│  │  ├─ classifier.py
│  │  ├─ budget.py
│  │  ├─ signal.py
│  │  └─ models.py
│  ├─ intraday/
│  │  ├─ tracker.py
│  │  ├─ signal.py
│  │  └─ models.py
│  ├─ execution/
│  │  ├─ models.py
│  │  ├─ router.py
│  │  ├─ mock_broker.py
│  │  ├─ moomoo_broker.py
│  │  └─ ib_broker.py
│  ├─ backtest/
│  │  ├─ engine.py
│  │  ├─ runner.py
│  │  ├─ metrics.py
│  │  └─ report.py
│  ├─ loggingx/
│  │  ├─ logger.py
│  │  └─ event_store.py
│  └─ utils/
│     ├─ time.py
│     ├─ mathx.py
│     └─ validation.py
├─ scripts/
│  ├─ init_db.py
│  ├─ add_symbol.py
│  ├─ update_daily_data.py
│  ├─ update_intraday_data.py
│  ├─ run_backtest.py
│  ├─ run_paper.py
│  └─ run_live.py
└─ tests/
   ├─ test_data_layer.py
   ├─ test_symbol_manager.py
   ├─ test_virtual_account.py
   ├─ test_trend_engine.py
   ├─ test_intraday_engine.py
   ├─ test_execution_engine.py
   └─ test_backtest_engine.py
```

---

# 4. 运行模式定义

## 4.1 backtest
用途：
- 用历史数据按时间推进
- 使用虚拟账户
- 使用 mock execution

数据源：
- 本地 daily.db
- 本地 intraday.db

账户源：
- 本地虚拟账户

执行源：
- mock broker

---

## 4.2 paper
用途：
- 实时仿真
- 可使用券商或实时数据源
- 不真实下单

数据源：
- moomoo / ib / 本地缓存

账户源：
- 本地虚拟账户或 paper account

执行源：
- mock broker

---

## 4.3 live
用途：
- 实盘运行

数据源：
- 券商实时数据
- 本地缓存辅助

账户源：
- 实际券商账户

执行源：
- 实际券商下单接口

---

# 5. 数据结构定义（Schema）

## 5.1 OHLCVBar
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class OHLCVBar:
    datetime: datetime
    ticker: str
    interval: str        # "1d" / "15m"
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    update_time: datetime
```

字段说明：
- `datetime`: bar 所属时间
- `ticker`: 标的代码
- `interval`: K线周期
- `source`: yfinance / moomoo / ib / local
- `update_time`: 写入数据库时间

约束：
- `(ticker, interval, datetime)` 唯一
- `high >= max(open, close, low)`
- `low <= min(open, close, high)`

---

## 5.2 SymbolInfo
```python
from dataclasses import dataclass, field

@dataclass
class SymbolInfo:
    symbol: str
    market: str
    asset_type: str
    currency: str
    timezone: str

    enabled_for_backtest: bool = True
    enabled_for_live: bool = False
    enabled_for_paper: bool = True

    tags: list[str] = field(default_factory=list)

    data_provider: str | None = None
    broker_route: str | None = None
    strategy_profile: str | None = None

    base_trade_amount_usd: float | None = None
    max_position_usd: float | None = None
    weekly_budget_multiplier: float | None = None

    allow_force_buy_last_bar: bool = True
    allow_fractional: bool = False
```

补充约束：
- `symbol` 唯一
- `asset_type` 允许值：`stock`, `etf`
- `base_trade_amount_usd > 0`
- `max_position_usd >= base_trade_amount_usd`
- `weekly_budget_multiplier >= 1`

---

## 5.3 AccountSnapshot
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class AccountSnapshot:
    snapshot_time: datetime
    mode: str
    account_id: str
    cash_available: float
    cash_total: float
    equity_value: float
    market_value: float
    total_asset: float
```

---

## 5.4 Position
```python
from dataclasses import dataclass

@dataclass
class Position:
    ticker: str
    quantity: float
    avg_cost: float
    market_price: float
    market_value: float
    unrealized_pnl: float
```

---

## 5.5 TradeRecord
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TradeRecord:
    trade_id: str
    order_id: str
    ticker: str
    side: str              # buy / sell
    quantity: float
    price: float
    amount: float
    fee: float
    trade_time: datetime
    mode: str              # backtest / paper / live
    broker: str
    note: str | None = None
```

---

## 5.6 OrderRequest
```python
from dataclasses import dataclass

@dataclass
class OrderRequest:
    ticker: str
    side: str
    order_type: str        # market / limit
    price: float | None
    amount_usd: float
    quantity: float | None
    reason: str
    strategy_tag: str | None = None
```

---

## 5.7 OrderStatus
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class OrderStatus:
    order_id: str
    ticker: str
    side: str
    status: str            # submitted / partial / filled / canceled / rejected
    submit_time: datetime
    update_time: datetime
    submitted_price: float | None
    avg_fill_price: float | None
    filled_quantity: float
    filled_amount: float
    broker_message: str | None = None
```

---

## 5.8 TrendFeatures
```python
from dataclasses import dataclass
from datetime import date

@dataclass
class TrendFeatures:
    trade_date: date
    ticker: str
    close: float
    ma5: float
    ma20: float
    ma60: float
    slope5: float
    slope20: float
    slope60: float
    ma_order_code: str
    slope_code: str
```

说明：
- `ma_order_code`: 例如 `5>20>60`, `20>5>60`
- `slope_code`: 例如 `+,+,+`, `+,+,-`

---

## 5.9 TrendDecision
```python
from dataclasses import dataclass
from datetime import date

@dataclass
class TrendDecision:
    trade_date: date
    ticker: str
    trend_type: str
    trend_strength: float
    action_bias: str           # buy_bias / sell_bias / hold_bias
    buy_threshold_pct: float | None
    sell_threshold_pct: float | None
    rebound_pct: float | None
    budget_multiplier: float
    reason: str
```

---

## 5.10 DailySignal
```python
from dataclasses import dataclass
from datetime import date

@dataclass
class DailySignal:
    trade_date: date
    ticker: str
    action: str                # buy / sell / hold
    target_price: float | None
    planned_amount_usd: float
    allowed_cash_today: float
    final_amount_usd: float
    reason: str
```

---

## 5.11 IntradayState
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class IntradayState:
    ticker: str
    trade_date: str
    tracking_side: str         # buy / sell
    tracked_low: float | None
    tracked_high: float | None
    current_order_id: str | None
    order_active: bool
    entered_trade: bool
    force_trade_enabled: bool
    last_bar_time: datetime | None
    note: str | None = None
```

---

## 5.12 LogEvent
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class LogEvent:
    event_time: datetime
    level: str
    module: str
    event_type: str
    ticker: str | None
    message: str
    payload_json: str | None
```

---

# 6. 数据库设计

使用 SQLite，建议 4 个数据库文件：

- `daily.db`
- `intraday.db`
- `symbols.db`
- `account.db`

如后期需要，也可统一为单库多表。

---

## 6.1 daily.db

### 表：daily_bars
字段：
- ticker TEXT
- datetime TEXT
- interval TEXT
- open REAL
- high REAL
- low REAL
- close REAL
- volume REAL
- source TEXT
- update_time TEXT

主键：
- `(ticker, interval, datetime)`

索引：
- `(ticker, datetime)`

---

## 6.2 intraday.db

### 表：intraday_bars
字段同上，`interval` 固定为 `15m`

主键：
- `(ticker, interval, datetime)`

索引：
- `(ticker, datetime)`

---

## 6.3 symbols.db

### 表：symbols
映射 `SymbolInfo`

主键：
- `symbol`

---

## 6.4 account.db

### 表：account_snapshots
### 表：positions
### 表：trade_records
### 表：orders

---

# 7. 配置文件规范

建议使用 YAML。

## 7.1 最小配置示例
```yaml
mode: backtest

timezone: America/New_York

data:
  daily_provider: local
  intraday_provider: local
  daily_db_path: data/daily.db
  intraday_db_path: data/intraday.db

account:
  account_source: local_virtual
  initial_cash: 100000

execution:
  broker: mock
  allow_fractional_default: false

logging:
  log_level: INFO
  log_dir: logs/

strategy:
  ma_windows: [5, 20, 60]
  intraday_interval: 15m
  last_bar_force_trade: true
```

---

# 8. 模块详细接口定义

# 8.1 Runtime Controller

文件：
- `app/runtime/controller.py`

职责：
- 加载配置
- 初始化上下文
- 初始化 logger
- 根据 mode 注入 provider / account / broker 实现

## 接口
```python
def init_runtime(config_path: str) -> dict:
    ...
```

输入：
- `config_path`: 配置文件路径

输出：
- `runtime_context: dict`

返回结构建议：
```python
{
    "mode": "backtest",
    "config": {...},
    "logger": logger_obj,
    "daily_provider": provider_obj,
    "intraday_provider": provider_obj,
    "symbol_manager": symbol_manager_obj,
    "account_manager": account_manager_obj,
    "execution_engine": execution_engine_obj,
}
```

---

# 8.2 Data Layer

## 8.2.1 Provider 抽象基类

文件：
- `app/data/providers/base.py`

```python
class BaseDataProvider:
    def fetch_bars(
        self,
        ticker: str,
        interval: str,
        start_date,
        end_date,
    ):
        raise NotImplementedError
```

---

## 8.2.2 yfinance provider

文件：
- `app/data/providers/yfinance_provider.py`

职责：
- 获取历史日线数据
- 获取短周期日内数据（若可用）
- 做字段标准化

接口：
```python
def fetch_bars(ticker: str, interval: str, start_date, end_date) -> "pd.DataFrame":
    ...
```

输入：
- `ticker`
- `interval`: `1d` / `15m`
- `start_date`
- `end_date`

输出 DataFrame 标准列：
- `datetime`
- `ticker`
- `interval`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `source`
- `update_time`

特殊要求：
- 自动排序
- 自动去重
- 统一时区
- 若字段为空，抛出明确错误

---

## 8.2.3 moomoo provider
先保留接口，不要求首版全部实现。

---

## 8.2.4 ib provider
先保留接口，不要求首版全部实现。

---

## 8.2.5 数据清洗函数

文件：
- `app/data/schema.py`

```python
def normalize_ohlcv_dataframe(df, ticker: str, interval: str, source: str):
    ...
```

职责：
- 重命名列
- 补全 ticker / interval / source
- 转 datetime
- 去重
- 排序
- 检查数值合法性

---

## 8.2.6 数据库存储

文件：
- `app/data/repository.py`

### 接口 1
```python
def save_bars(df, db_path: str, table_name: str) -> int:
    ...
```

输入：
- 标准 OHLCV DataFrame
- db 路径
- 表名

输出：
- 写入 / 更新的记录数

### 接口 2
```python
def load_bars(
    db_path: str,
    table_name: str,
    ticker: str,
    start_date=None,
    end_date=None,
):
    ...
```

输出：
- 标准 OHLCV DataFrame

### 接口 3
```python
def init_price_db(db_path: str, table_name: str) -> None:
    ...
```

---

## 8.2.7 数据更新器

文件：
- `app/data/updater.py`

### 接口
```python
def update_symbol_data(
    ticker: str,
    interval: str,
    provider,
    db_path: str,
    table_name: str,
    start_date,
    end_date,
) -> dict:
    ...
```

输出：
```python
{
    "ticker": "SPY",
    "interval": "1d",
    "fetched_rows": 252,
    "saved_rows": 252,
    "status": "ok"
}
```

---

# 8.3 Symbol Manager

文件：
- `app/symbols/manager.py`

职责：
- 增加 / 查询 / 修改标的配置
- 读取策略参数
- 为其他模块提供 symbol 配置

## 接口 1：新增标的
```python
def add_symbol(symbol_info: SymbolInfo) -> None:
    ...
```

## 接口 2：查询标的
```python
def get_symbol(symbol: str) -> SymbolInfo:
    ...
```

## 接口 3：更新标的
```python
def update_symbol(symbol: str, updates: dict) -> None:
    ...
```

## 接口 4：列出全部启用标的
```python
def list_enabled_symbols(mode: str) -> list[SymbolInfo]:
    ...
```

规则：
- `mode="backtest"` → 返回 `enabled_for_backtest=True`
- `mode="paper"` → 返回 `enabled_for_paper=True`
- `mode="live"` → 返回 `enabled_for_live=True`

---

# 8.4 Account Manager

职责：
- 统一账户查询接口
- 在 backtest / paper 模式使用虚拟账户
- 在 live 模式连接真实券商账户

---

## 8.4.1 统一接口

文件：
- `app/account/manager.py`

```python
class BaseAccountManager:
    def get_account_snapshot(self) -> AccountSnapshot:
        ...
    def get_position(self, ticker: str) -> Position | None:
        ...
    def get_recent_trade_stats(self, ticker: str, as_of_date) -> dict:
        ...
    def apply_trade(self, trade_record: TradeRecord) -> None:
        ...
```

---

## 8.4.2 最近交易统计输出格式

```python
{
    "ticker": "SPY",
    "buy_count_5d": 2,
    "buy_amount_5d": 1200.0,
    "sell_count_5d": 0,
    "sell_amount_5d": 0.0,
    "trade_count_week": 3,
    "trade_amount_week": 1800.0,
}
```

---

## 8.4.3 虚拟账户

文件：
- `app/account/virtual_account.py`

### 初始化接口
```python
def reset_virtual_account(initial_cash: float) -> None:
    ...
```

逻辑：
- 清空旧持仓
- 清空旧订单
- 清空旧交易记录
- 写入初始资金

### 查询接口
```python
def get_account_snapshot() -> AccountSnapshot:
    ...
```

### 更新接口
```python
def apply_filled_trade(trade_record: TradeRecord) -> None:
    ...
```

逻辑：
- buy：减少现金，增加持仓
- sell：增加现金，减少持仓
- 重新计算持仓均价 / 市值

---

# 8.5 Trend Engine

职责：
- 基于日线数据计算趋势特征
- 生成趋势状态
- 计算当天允许交易金额
- 生成日级别交易信号

---

## 8.5.1 特征计算

文件：
- `app/trend/features.py`

### 接口
```python
def compute_ma_features(df, ma_windows=(5, 20, 60)):
    ...
```

输入：
- 日线 DataFrame，至少包含 60 天数据

输出：
- 增强后的 DataFrame，新增列：
  - `ma5`
  - `ma20`
  - `ma60`
  - `slope5`
  - `slope20`
  - `slope60`
  - `ma_order_code`
  - `slope_code`

---

## 8.5.2 趋势分类

文件：
- `app/trend/classifier.py`

### 接口
```python
def classify_trend(row) -> TrendDecision:
    ...
```

首版分类逻辑：
- 使用 `ma5 / ma20 / ma60` 的相对大小关系
- 使用 slope 正负号
- 输出：
  - `trend_type`
  - `trend_strength`
  - `buy_threshold_pct`
  - `rebound_pct`
  - `budget_multiplier`
  - `reason`

建议首版趋势类型：
- `strong_uptrend`
- `weak_uptrend`
- `range`
- `weak_downtrend`
- `strong_downtrend`
- `rebound_setup`

---

## 8.5.3 今日可用资金计算

文件：
- `app/trend/budget.py`

### 接口
```python
def compute_allowed_cash_today(
    symbol_info: SymbolInfo,
    account_snapshot: AccountSnapshot,
    recent_trade_stats: dict,
) -> float:
    ...
```

考虑因子：
- `base_trade_amount_usd`
- `max_position_usd`
- `weekly_budget_multiplier`
- 当前可用现金
- 过去 5 日买入次数 / 金额
- 本周交易金额

目标：
- 不允许过早用完本周预算
- 不允许超持仓上限
- 不允许超过账户可用现金

---

## 8.5.4 当日交易金额

文件：
- `app/trend/signal.py`

### 接口
```python
def compute_trade_amount(
    allowed_cash_today: float,
    budget_multiplier: float,
    account_snapshot: AccountSnapshot,
) -> float:
    ...
```

逻辑：
- `trade_amount = allowed_cash_today * budget_multiplier`
- 但不得超过：
  - `allowed_cash_today`
  - `cash_available`

---

## 8.5.5 日级信号生成

### 接口
```python
def generate_daily_signal(
    latest_daily_row,
    trend_decision: TrendDecision,
    symbol_info: SymbolInfo,
    account_snapshot: AccountSnapshot,
    recent_trade_stats: dict,
) -> DailySignal:
    ...
```

输出：
- `action`
- `target_price`
- `planned_amount_usd`
- `final_amount_usd`
- `reason`

首版买入目标价建议：
- 用前日收盘价或当日开盘价为基准
- 结合 `buy_threshold_pct` 生成买入阈值

---

# 8.6 Intraday Engine

职责：
- 日内 15min bar 追踪
- 判断低点 / 高点是否停止延续
- 触发下单、撤单、强制成交

---

## 8.6.1 买入追踪器

文件：
- `app/intraday/tracker.py`

### 接口
```python
def init_intraday_state(ticker: str, trade_date: str, tracking_side: str) -> IntradayState:
    ...
```

### 接口
```python
def update_buy_tracking_state(state: IntradayState, bar, target_price: float, rebound_pct: float) -> dict:
    ...
```

输出示例：
```python
{
    "state": state,
    "event": "continue_tracking",   # continue_tracking / place_order / cancel_order / done
    "order_request": None,
    "reason": "new low detected"
}
```

---

## 8.6.2 买入逻辑详细规则

### 规则 A：更新 tracked_low
若当前 15min bar 的 `low` 小于 `tracked_low`：
- 更新 `tracked_low`
- 若有未成交订单，后续可触发撤单逻辑

### 规则 B：反弹确认
若当前价格相对 `tracked_low` 反弹达到 `rebound_pct`，且 `tracked_low <= target_price`：
- 生成买单请求

### 规则 C：更低点撤单
若已有挂单且出现更低点：
- 检查订单状态
- 若未成交 → 撤单 → 回到追踪模式
- 若已成交 → 当日结束

### 规则 D：尾盘强制成交
最后 15 分钟，若：
- 今日尚未成交
- 当前价格 <= target_price
- `allow_force_buy_last_bar=True`
则生成强制买单请求

---

## 8.6.3 卖出逻辑
首版只保留接口，不实现复杂逻辑。

---

# 8.7 Execution Engine

职责：
- 统一下单接口
- 路由至 mock / moomoo / ib
- 返回订单状态
- 支持撤单

---

## 8.7.1 统一接口

文件：
- `app/execution/router.py`

```python
class BaseBroker:
    def place_order(self, order_request: OrderRequest) -> OrderStatus:
        ...
    def cancel_order(self, order_id: str) -> OrderStatus:
        ...
    def get_order_status(self, order_id: str) -> OrderStatus:
        ...
```

---

## 8.7.2 Mock Broker

文件：
- `app/execution/mock_broker.py`

规则：
- market 单：按当前价立即成交
- limit 单：首版可直接近似为当下 bar 内可成交则成交
- 写入 orders / trades
- 调用 virtual account 更新持仓

---

## 8.7.3 下单数量计算

### 接口
```python
def build_order_request(
    ticker: str,
    side: str,
    amount_usd: float,
    price: float,
    allow_fractional: bool,
    reason: str,
) -> OrderRequest:
    ...
```

逻辑：
- `quantity = amount_usd / price`
- 若 `allow_fractional=False` → 向下取整
- 若 quantity <= 0 → 拒绝下单

---

# 8.8 Logging System

职责：
- 记录系统关键动作
- 支持调试 / 审计 / 回测解释

文件：
- `app/loggingx/logger.py`

## 接口
```python
def log_event(level: str, module: str, event_type: str, message: str, ticker: str | None = None, payload: dict | None = None):
    ...
```

日志类别建议：
- `system_init`
- `data_update`
- `daily_signal`
- `intraday_track`
- `order_submit`
- `order_cancel`
- `order_fill`
- `account_update`
- `error`

---

# 8.9 Backtest Engine

职责：
- 按历史时间推进
- 对每个交易日运行同一套逻辑
- 使用虚拟账户执行成交
- 输出绩效结果

文件：
- `app/backtest/engine.py`

## 接口
```python
def run_backtest(
    ticker: str,
    start_date,
    end_date,
    runtime_context: dict,
) -> dict:
    ...
```

---

## 8.9.1 回测主流程

对每个交易日：

1. 读取截至该日的历史日线数据
2. 计算 MA 特征
3. 分类趋势
4. 读取 symbol 配置
5. 读取账户快照与最近交易统计
6. 生成 DailySignal
7. 若 action=buy：
   - 读取该日 15min 数据
   - 运行 Intraday Engine
   - 通过 Mock Broker 执行
8. 写入 trade / order / log / decision
9. 推进到下一交易日

---

## 8.9.2 回测输出格式

```python
{
    "ticker": "SPY",
    "start_date": "2025-01-01",
    "end_date": "2026-03-31",
    "total_return": 0.12,
    "max_drawdown": -0.08,
    "trade_count": 27,
    "win_rate": 0.63,
    "equity_curve_df": ...,
    "trade_records_df": ...,
    "decision_records_df": ...,
}
```

---

# 9. 首版实现边界（MVP）

为了尽快可跑通，首版只实现以下组合：

## 9.1 数据源
- yfinance
- local sqlite

## 9.2 账户
- local virtual account

## 9.3 执行
- mock broker

## 9.4 策略
- 买入策略
- 卖出策略先保留接口
- 黑天鹅先保留接口

## 9.5 标的
- 先支持单标的
- 先支持美股 ETF / 个股

## 9.6 趋势
- 基于 MA5 / MA20 / MA60
- 基于 slope 正负
- 先实现 5 类趋势

---

# 10. 开发顺序（必须按顺序）

## 第 1 阶段：基础设施
1. 建目录结构
2. 建 dataclass schema
3. 建 sqlite 初始化脚本
4. 建 logger
5. 建 config loader

## 第 2 阶段：数据层
6. 实现 yfinance provider
7. 实现 normalize dataframe
8. 实现 save/load/update db
9. 写 `test_data_layer.py`

## 第 3 阶段：标的与账户
10. 实现 SymbolManager
11. 实现 VirtualAccount
12. 实现 trade / position / snapshot 更新
13. 写 `test_symbol_manager.py`
14. 写 `test_virtual_account.py`

## 第 4 阶段：趋势引擎
15. 实现 MA feature
16. 实现 trend classifier
17. 实现 budget 计算
18. 实现 daily signal
19. 写 `test_trend_engine.py`

## 第 5 阶段：日内逻辑
20. 实现 intraday tracker
21. 实现 place/cancel/force trade 条件
22. 写 `test_intraday_engine.py`

## 第 6 阶段：执行层
23. 实现 build_order_request
24. 实现 mock broker
25. 接入 virtual account
26. 写 `test_execution_engine.py`

## 第 7 阶段：回测引擎
27. 实现 run_backtest
28. 输出 trade log / decision log / metrics
29. 写 `test_backtest_engine.py`

---

# 11. 测试要求

## 11.1 数据层测试
至少测试：
- ticker=`SPY`
- interval=`1d`
- 时间范围=`2025-01-01` 到 `2026-03-31`
- 成功获取数据
- 正确保存到 sqlite
- 读出数据行数 > 0
- 输出价格柱状图 / K线相关图为 png（后续可加）

---

## 11.2 虚拟账户测试
测试：
- 初始资金 10000
- 买入 1000 美元
- 检查现金减少
- 检查持仓增加
- 再次买入同 ticker，检查均价更新

---

## 11.3 趋势测试
测试：
- 正确生成 `ma5/20/60`
- 正确生成 slope
- 至少覆盖：
  - strong_uptrend
  - range
  - strong_downtrend

---

## 11.4 日内追踪测试
测试：
- 新低出现时 tracked_low 更新
- 达到 rebound 条件时生成订单
- 出现更低点时触发撤单
- 尾盘触发 force trade

---

## 11.5 回测测试
测试：
- 用单一 ticker 跑通完整流程
- 生成 trade_records
- 生成 summary metrics
- 回测无异常中断

---

# 12. 后续扩展接口

以下不在首版必须完成范围内，但要预留接口：

## 12.1 卖出引擎
- 趋势止盈
- 趋势止损
- 15min 卖出追踪

## 12.2 黑天鹅风控
- 跳空极端波动
- 熔断
- 数据缺失日
- 网络 / broker 异常

## 12.3 分位系统
- 历史回调分位
- 震荡周期分位
- 与趋势状态联动的动态买入阈值

## 12.4 多标的组合
- 多 ticker 轮询
- 组合总预算控制
- 不同资产类别分配

## 12.5 实盘接入
- moomoo broker
- ib broker
- 真实订单状态同步
- 断线恢复

---

# 13. 对 Codex 的明确实现要求

Codex 生成代码时，必须遵守：

1. 所有模块都必须可独立 import
2. 每个模块必须有最小可运行测试
3. 所有函数必须有 type hints
4. 所有关键步骤必须有日志
5. 所有数据表字段名必须与本文件保持一致
6. 不允许在 UI 代码中混入策略计算
7. 回测与实盘必须复用同一套策略逻辑
8. 先实现 MVP，不要提前实现复杂卖出 / 黑天鹅 / 期权逻辑
9. 所有异常必须抛出明确错误信息
10. 生成代码时优先保证可运行，再做美化和抽象

---

# 14. 当前建议的首个代码任务

Codex 第一轮应完成以下文件：

```text
app/data/providers/yfinance_provider.py
app/data/schema.py
app/data/repository.py
app/data/updater.py
tests/test_data_layer.py
scripts/init_db.py
scripts/update_daily_data.py
```

完成目标：
- 建立 sqlite 数据库
- 拉取 SPY 2025-01-01 至 2026-03-31 的日线数据
- 保存到 daily.db
- 能从数据库读回
- 测试通过

---

# 15. 当前不应做的事情

为了避免跑偏，首轮不要做：
- 不要做 UI
- 不要做 Streamlit
- 不要做复杂卖出
- 不要做多标的组合
- 不要做期权
- 不要做复杂风控
- 不要做过度抽象的插件系统

先把：
**数据层 → 虚拟账户 → 趋势 → 日内买入 → 回测**
这条最短路径跑通。

---

# 16. 最终一句话定义

这是一个以**本地数据库 + 模块复用 + 可回测可实盘迁移**为核心原则的自动交易系统，首版目标不是“功能最全”，而是“结构正确、接口稳定、能真实跑通最短闭环”。

# 17. 文档治理与版本管理规范（新增）

## 17.1 文档分层结构

系统文档必须分为三层：

### 1. 主文档（system_design.md）
- 定义系统架构
- 定义模块边界
- 定义数据结构与接口
- 不允许写实现细节

### 2. 模块文档（/docs/modules/）
每个模块单独维护：
- data_layer.md
- trend_engine.md
- intraday_engine.md
- execution_engine.md
- backtest_engine.md

统一结构：

## 目标
## 输入
## 输出
## 核心逻辑
## 状态变量
## 边界条件
## MVP范围
## 测试方案

### 3. 策略研究文档（/docs/research/）
用于探索：
- 分位系统
- Markov状态
- 参数优化

该层可以推翻，不影响系统结构。

---

## 17.2 文档驱动开发流程（强制）

所有开发必须遵循：

1. 修改文档（而不是代码）
2. 生成明确开发任务
3. 由 Codex 实现代码
4. 编写测试验证
5. 更新变更记录

禁止：
- 直接修改代码绕过文档
- 未记录的策略变更

---

## 17.3 变更记录（changelog）

路径：
/docs/changelog.md

格式：

## 日期

### 修改
- 描述修改内容

### 原因
- 为什么修改

### 影响范围
- 模块列表

---

## 17.4 文档与代码一致性原则

必须保证：

- 文档字段 == 数据库字段
- 文档接口 == 代码接口
- 文档逻辑 == 策略逻辑

任何不一致必须优先修复文档。

---

## 17.5 版本控制规范

提交必须拆分：

docs: 文档修改
feat: 功能实现
test: 测试增加
fix: bug修复

禁止混合提交。

---

## 17.6 当前版本标记

版本：v0.2  
状态：进入“文档驱动开发阶段”  
目标：完成 Data Layer → Backtest MVP 闭环

---

# 结束说明

本系统进入工程化阶段，后续所有开发必须遵循：
文档 → 任务 → 代码 → 测试 → 回测

禁止跳步骤开发。
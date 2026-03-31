# 自动交易平台系统开发文档

## 一、系统功能定义
本系统为一个完整的自动交易平台，具备以下能力：
- 数据获取与更新
- 标的管理
- 资金管理
- 趋势分析
- 日内高低点追踪
- 自动下单与撤单
- 完备的日志管理
- 24小时独立运行

附加：
- 回测引擎（复用所有模块）
- 回测结果输出与可视化

---

## 二、系统运行逻辑

### A. 数据准备
- 获取/更新过去1年日线数据（open, close, high, low, volume）
- 存储至本地数据库
- 计算趋势特征
- 输出下一日趋势形态及概率

### B. 标的配置读取
从标的管理模块获取：
- 标的类型（ETF / 个股）
- 每日基准金额
- 单日购买上限
- 每周购买上限
- 不同趋势下的买卖系数

### C. 账户状态读取
从资金管理模块获取：
- 当前可用现金
- 过去5日该标的交易次数及总量
- 本周交易次数及总量

### D. 决策计算
汇总 A + B + C：
- 买卖判断（Buy / Sell / Hold）
- 目标价格
- 交易参数
- 使用资金

### E. 决策执行
- E1：若需交易 → 进入日内策略（F）
- E2：记录决策依据与结果

### F. 日内交易策略
- F1：追踪日内高/低点，判断拐点后下单
- F2：最后15分钟强制执行
- F3：极端情况处理（预留接口）

---

## 三、模块结构与接口定义

### 0. 运行模式与初始化
- 回测 / 模拟 / 实盘
- 确定数据源与账户源
- 初始化连接与数据
- 初始化日志系统

---

## 1. 数据层（Data Layer）

### 功能
- 数据获取
- 数据清洗
- 本地存储（SQLite）

### 数据库结构
- 日线数据库
- 15min 日内数据库

### 1.1 数据获取统一接口
输入：
- datetime, ticker, interval, start_date, end_date, source

输出 DataFrame：
- datetime, ticker, interval
- open, close, high, low, volume
- source, update_date

### 1.1.1 数据源实现
- yfinance
- moomoo
- IB

### 1.2 数据库初始化
### 1.3 新增 ticker
### 1.4 更新数据
### 1.5 读取日线数据
### 1.6 读取15min数据
### 1.7 数据读写测试

---

## 2. 标的管理模块

### 数据结构（核心）
```python
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

### 功能接口
- 2.1 标的新增（CLI / Prompt输入）
- 2.2 标的查询
- 2.3 标的修改
- 可扩展为数据库存储

---

## 3. 资金管理模块

### 功能
- 获取账户状态
- 管理资金使用

### 3.1 基础接口
输入：
- ticker

输出：
- 当前账户资金
- 过去5日交易统计
- 本周交易统计

### 3.1.1 券商接口
- moomoo
- IB

### 3.1.2 本地虚拟账户
#### 初始化
- 输入初始资金
- 重置交易记录

#### 数据结构
- 账户资金表
- 交易记录表

#### 功能
- 读取账户
- 更新账户（下单/成交）

---

## 4. 趋势判断模块

### 4.1 核心策略
基于：
- MA5 / MA20 / MA60 排列
- MA斜率

输出：
- 趋势类型
- 趋势强度
- 买卖阈值

### 4.2 资金系数计算
输入：
- 基准金额
- 最大金额
- 历史交易记录

输出：
- 今日可用资金

### 4.3 当日交易金额计算
结合：
- 趋势强度
- 可用资金

### 4.4 卖出模块
- 预留接口

### 4.5 测试模块
输出：
- 每日判断
- 理由
- CSV/数据库

---

## 5. 日内交易策略模块

### 5.1 买入策略

#### 5.1.1 低点追踪
- 跟踪15min最低价
- 最低价停止下降 + 出现反弹 → 下单

#### 5.1.2 动态撤单
- 若出现更低点：
  - 未成交 → 撤单
  - 已成交 → 结束

#### 5.1.3 收盘强制执行
- 最后15分钟
- 未成交 → 强制下单

### 5.2 卖出策略
- 预留接口

### 5.3 黑天鹅事件
- 预留接口

---

## 6. 下单模块

### 6.1 基础接口
输入：
- ticker
- 当前价格
- 交易金额

输出：
- 下单执行

### 6.1.1 券商接口
- moomoo
- IB

### 6.1.2 虚拟下单
- 按当前价格成交
- 更新账户与交易记录
- 后续可加入滑点/手续费

---

## 四、日志系统（Log System）

建议包含：
- 模块级日志
- 决策日志
- 交易日志
- 错误日志

支持：
- 文件输出
- 控制台输出
- 分级（INFO / DEBUG / ERROR）

---

## 五、回测引擎

### 功能
- 调用全部模块
- 使用本地数据
- 使用虚拟账户

### 输出
- 收益曲线
- 交易记录
- 指标分析（胜率 / 回撤 / 夏普等）

---

## 六、系统扩展方向

- 卖出策略完善
- 黑天鹅处理
- 多标的组合优化
- 风控模块
- 分位系统（Pullback核心）
- 期权模块接入

# 特征值计算脚本开发文档（供 Codex 实现）

## 1. 文档目标

本文件用于驱动 Codex 在 `scripts/` 下实现一个**趋势研究用特征值计算脚本**。  
该脚本不负责交易、不负责回测、不负责可视化，只负责：

1. 复用 `app/` 下已有的数据获取 / 数据更新 / 数据读取相关函数
2. 针对一个或多个 ticker 拉取并准备日线数据
3. 计算指定特征值
4. 计算对应百分位
5. 将结果同时保存为：
   - 一个汇总 SQLite 文件（包含全部 ticker）
   - 每个 ticker 一个独立 CSV 文件

本脚本定位为**研究工具**，用于后续趋势模块、状态编码、分位系统研究，不直接写入正式策略模块。

---

## 2. 实现位置

建议新增以下文件：

```text
scripts/compute_trend_features.py
```

如有必要，可在 `app/` 下补充少量可复用函数，但**本次的特征计算主流程应放在 `scripts/` 下**，避免在策略尚未定型前过早沉入正式模块。

---

## 3. 设计原则

### 3.1 复用 app 下已有数据函数
必须优先复用以下已有能力，而不是在脚本里重复造轮子：

- `app/data/providers/...`
- `app/data/schema.py`
- `app/data/repository.py`
- `app/data/updater.py`

若现有函数不足，可在 `app/data/` 内新增小型辅助函数，但不要在 `scripts/` 中复制数据库逻辑。

### 3.2 计算与展示分离
本脚本只负责：
- 获取数据
- 计算特征
- 保存结果

不负责：
- Streamlit
- 图形展示
- UI

### 3.3 无未来函数
所有在时点 `t` 输出的特征，都必须只使用 `t-1, t-2, ...,` 更早的数据。  
**不得使用 `t` 当天的 close / high / low 来计算 `t` 的特征。**

### 3.4 样本不足输出 NaN
若 warmup 后数据仍不足以支撑某项计算，必须输出 `NaN`，不得用 0、前值填充、或强行缩窗。

### 3.5 多 ticker 支持
允许输入多个 ticker。  
输出规则：

- SQLite：一个文件，包含所有 ticker 的结果
- CSV：每个 ticker 单独一个文件

---

## 4. 输入与输出要求

## 4.1 输入参数

脚本至少应支持以下输入参数（CLI 或 main 内可配置均可）：

```python
tickers: list[str]
start_date: str        # 研究输出起始日期，例如 "2024-01-01"
end_date: str          # 研究输出结束日期，例如 "2026-03-31"
daily_db_path: str     # 日线数据库路径
output_sqlite_path: str
output_csv_dir: str
use_update: bool       # 是否先调用 app 下的数据更新逻辑
provider_name: str     # 默认 local；必要时允许 yfinance
```

### 4.1.1 多 ticker 示例

```python
tickers = ["SPY", "QQQ", "NVDA"]
start_date = "2024-01-01"
end_date = "2026-03-31"
```

---

## 4.2 输出文件

### 4.2.1 SQLite
输出一个汇总 sqlite 文件，例如：

```text
data/processed/trend_features.db
```

要求包含所有 ticker 的结果表，例如：

- 表名：`trend_features_daily`

### 4.2.2 CSV
每个 ticker 一个独立 csv 文件，例如：

```text
data/processed/features/SPY_trend_features.csv
data/processed/features/QQQ_trend_features.csv
data/processed/features/NVDA_trend_features.csv
```

---

## 5. Warmup 数据范围要求

为了保证 MA、slope、百分位有足够历史，脚本在拉取或读取数据时，不能只取用户输入的 `start_date ~ end_date`。

必须自动扩展 warmup 区间。

### 5.1 基本要求

若用户要求输出起点为：

```text
start_date = 2024-01-01
```

则数据准备时，至少应向前扩展到：

```text
2023-01-01
```

即：**默认向前扩展 1 个自然年**。

### 5.2 实现规则

建议：

```python
fetch_start_date = start_date - 1 calendar year
```

例如：

- 输出起点：`2024-01-01`
- 实际取数起点：`2023-01-01`

### 5.3 不足样本处理

即使已经扩展 1 年 warmup，若某些特征仍因历史样本不足而无法计算，则该位置输出 `NaN`。

不得：
- 缩短回看窗口
- 用 0 替代
- 用最近值填充

---

## 6. 数据准备流程

对每个 ticker：

1. 根据 `start_date` 计算 `fetch_start_date = start_date - 1 year`
2. 若 `use_update=True`：
   - 调用 `app/data/updater.py` 中已有更新函数，将 `fetch_start_date ~ end_date` 数据更新到 `daily.db`
3. 从 `daily.db` 读取该 ticker 的 `1d` 数据
4. 对读取结果做标准化：
   - 按日期升序
   - 去重
   - 检查必要列：`datetime/open/high/low/close/volume`
5. 在完整 warmup 数据上计算特征
6. 最终只保留 `start_date ~ end_date` 区间输出到结果表 / csv

---

## 7. 特征计算总原则

下面所有特征均按“在时点 `t` 计算”的角度定义。  
**在 `t` 时，允许使用的数据只能到 `t-1` 为止。**

记号约定：

- `Close_k`：第 `k` 天收盘价
- `Low_k`：第 `k` 天最低价
- `High_k`：第 `k` 天最高价
- `MA_w(t)`：在时点 `t` 可用的、基于过去 `w` 个交易日收盘价计算的均线
- 交易日窗口默认按行滚动，不按自然日缺口插值

---

## 8. 需要计算的特征

## 8.1 MA

窗口：

- 5d
- 20d
- 60d
- 120d

定义：

```text
MA_w(t) = mean(Close_{t-1}, Close_{t-2}, ..., Close_{t-w})
```

即：

- `ma_5 = mean(Close_{t-1} ... Close_{t-5})`
- `ma_20 = mean(Close_{t-1} ... Close_{t-20})`
- `ma_60 = mean(Close_{t-1} ... Close_{t-60})`
- `ma_120 = mean(Close_{t-1} ... Close_{t-120})`

### 实现要求
必须先将 `close` 整体 `shift(1)`，再做 rolling mean，确保不使用 `t` 当天收盘价。

---

## 8.2 slope

窗口：

- 5d
- 20d
- 60d
- 120d

定义：

```text
slope_w(t) = 对 [Close_{t-w}, Close_{t-w+1}, ..., Close_{t-1}] 做线性拟合得到的斜率
```

更具体地说：

- 自变量 `x = [1, 2, ..., w]`
- 因变量 `y = [Close_{t-w}, ..., Close_{t-1}]`
- 用线性回归 `y = a*x + b`
- `slope_w(t) = a`

### 说明
- `slope_5`：过去 5 天 close 的线性拟合斜率
- `slope_20`：过去 20 天 close 的线性拟合斜率
- `slope_60`：过去 60 天 close 的线性拟合斜率
- `slope_120`：过去 120 天 close 的线性拟合斜率

### 实现要求
必须保证 `t` 时的 `slope_w(t)` 仅使用 `t-1` 及更早 close。  
可通过对 `close` 使用 rolling window，并确保窗口右端为 `t-1`。

---

## 8.3 slope 的百分位

窗口对应：

- `slope_pct_5`
- `slope_pct_20`
- `slope_pct_60`
- `slope_pct_120`

默认历史分位窗口：

- 252 个交易日（约 1 年）

定义：

对某个 `slope_w(t)`，其百分位使用**过去 252 个交易日内已经计算出的同类 slope 历史值**计算，且：

- 正值与负值分开计算
- 负值结果保留负号
- 0 输出 0
- 历史样本不足输出 `NaN`

形式化定义：

设：

```text
s = slope_w(t)
H_t = 历史上 t-1, t-2, ..., t-252 的 slope_w 值
```

则：

### 若 `s > 0`
```text
slope_pct_w(t) = 在 H_t 的正值子集中，<= s 的比例
```

### 若 `s < 0`
```text
slope_pct_w(t) = - 在 H_t 的负值子集的绝对值中，<= |s| 的比例
```

### 若 `s = 0`
```text
slope_pct_w(t) = 0
```

### 历史样本不足规则
若：
- 总历史不足 252 个交易日，或
- 同号子样本为空

则输出 `NaN`。

---

## 8.4 spread

计算以下三组：

- `spread_5_20 = ma_5 / ma_20 - 1`
- `spread_20_60 = ma_20 / ma_60 - 1`
- `spread_60_120 = ma_60 / ma_120 - 1`

定义：

```text
spread_5_20(t)   = MA_5(t) / MA_20(t) - 1
spread_20_60(t)  = MA_20(t) / MA_60(t) - 1
spread_60_120(t) = MA_60(t) / MA_120(t) - 1
```

### 实现要求
仅在对应 MA 都非空时计算，否则输出 `NaN`。

---

## 8.5 spread 的百分位

对应列：

- `spread_pct_5_20`
- `spread_pct_20_60`
- `spread_pct_60_120`

定义规则与 slope 百分位完全一致：

- 历史窗口：过去 252 个交易日
- 正负分开
- 负号保留
- 样本不足输出 `NaN`

---

## 8.6 low_dev

定义为：

**前一天 low 相对于 MA 的偏离率**

对应：

- `low_dev_ma5`
- `low_dev_ma20`
- `low_dev_ma60`
- `low_dev_ma120`

公式：

```text
low_dev_ma5(t)   = Low_{t-1} / MA_5(t) - 1
low_dev_ma20(t)  = Low_{t-1} / MA_20(t) - 1
low_dev_ma60(t)  = Low_{t-1} / MA_60(t) - 1
low_dev_ma120(t) = Low_{t-1} / MA_120(t) - 1
```

### 实现要求
必须使用 `low.shift(1)`，不得直接使用 `t` 当天 low。

---

## 8.7 low_dev 的百分位

对应列：

- `low_dev_pct_ma5`
- `low_dev_pct_ma20`
- `low_dev_pct_ma60`
- `low_dev_pct_ma120`

规则：

- 历史窗口：过去 252 个交易日
- 正负分开
- 负值保留负号
- 历史不足输出 `NaN`

---

## 8.8 high_dev

定义为：

**前一天 high 相对于 MA 的偏离率**

对应：

- `high_dev_ma5`
- `high_dev_ma20`
- `high_dev_ma60`
- `high_dev_ma120`

公式：

```text
high_dev_ma5(t)   = High_{t-1} / MA_5(t) - 1
high_dev_ma20(t)  = High_{t-1} / MA_20(t) - 1
high_dev_ma60(t)  = High_{t-1} / MA_60(t) - 1
high_dev_ma120(t) = High_{t-1} / MA_120(t) - 1
```

### 实现要求
必须使用 `high.shift(1)`，不得直接使用 `t` 当天 high。

---

## 8.9 high_dev 的百分位

对应列：

- `high_dev_pct_ma5`
- `high_dev_pct_ma20`
- `high_dev_pct_ma60`
- `high_dev_pct_ma120`

规则：

- 历史窗口：过去 252 个交易日
- 正负分开
- 负值保留负号
- 历史不足输出 `NaN`

---

## 9. 百分位计算统一规范

为避免重复实现，建议写一个可复用函数，例如：

```python
def compute_signed_rolling_percentile(
    series: pd.Series,
    history_window: int = 252,
) -> pd.Series:
    ...
```

### 统一规则

对 `series[t] = x_t`：

- 历史比较集合只取 `t-1 ... t-history_window`
- 不包含 `t`
- `x_t > 0`：在历史正值子集里计算 `<= x_t` 的比例
- `x_t < 0`：在历史负值子集绝对值里计算 `<= |x_t|` 的比例，再乘 `-1`
- `x_t == 0`：输出 `0`
- 历史不足 / 同号子集为空：输出 `NaN`

### 注意
这里的“历史不足”指的是：
- 过去有效历史记录数不足 `history_window`
- 或该特征本身在该时点之前有大量 `NaN` 导致有效可比样本不足

建议严格按“有效历史样本数是否达到 252”判断。

---

## 10. 建议输出字段

最终输出 DataFrame 至少包含以下列：

### 基础标识列
- `datetime`
- `ticker`
- `open`
- `high`
- `low`
- `close`
- `volume`

### MA
- `ma_5`
- `ma_20`
- `ma_60`
- `ma_120`

### slope
- `slope_5`
- `slope_20`
- `slope_60`
- `slope_120`

### slope 百分位
- `slope_pct_5`
- `slope_pct_20`
- `slope_pct_60`
- `slope_pct_120`

### spread
- `spread_5_20`
- `spread_20_60`
- `spread_60_120`

### spread 百分位
- `spread_pct_5_20`
- `spread_pct_20_60`
- `spread_pct_60_120`

### low_dev
- `low_dev_ma5`
- `low_dev_ma20`
- `low_dev_ma60`
- `low_dev_ma120`

### low_dev 百分位
- `low_dev_pct_ma5`
- `low_dev_pct_ma20`
- `low_dev_pct_ma60`
- `low_dev_pct_ma120`

### high_dev
- `high_dev_ma5`
- `high_dev_ma20`
- `high_dev_ma60`
- `high_dev_ma120`

### high_dev 百分位
- `high_dev_pct_ma5`
- `high_dev_pct_ma20`
- `high_dev_pct_ma60`
- `high_dev_pct_ma120`

---

## 11. SQLite 保存要求

### 11.1 文件
输出一个 sqlite 文件，例如：

```text
data/processed/trend_features.db
```

### 11.2 表名
建议表名：

```text
trend_features_daily
```

### 11.3 主键建议
建议将以下组合作为唯一键：

```text
(ticker, datetime)
```

### 11.4 保存规则
- 所有 ticker 结果写入同一张表
- 允许覆盖同一 `(ticker, datetime)` 的旧结果
- 写入前保证 `datetime` 标准化
- 写入后应可按 ticker 查询

---

## 12. CSV 保存要求

对每个 ticker，导出一个独立 CSV，例如：

```text
data/processed/features/SPY_trend_features.csv
data/processed/features/QQQ_trend_features.csv
```

要求：

- 文件名包含 ticker
- 内容只包含该 ticker 的结果
- 日期升序
- 仅保留 `start_date ~ end_date` 的结果区间
- 编码采用 UTF-8

---

## 13. 建议脚本结构

```python
def main():
    # 1. 解析输入参数
    # 2. 计算 fetch_start_date
    # 3. 对每个 ticker 执行：
    #    a. update data（可选）
    #    b. load data
    #    c. compute features on full warmup range
    #    d. clip to output range
    #    e. save per-ticker csv
    # 4. merge all ticker results
    # 5. save sqlite
```

建议拆分函数：

```python
def compute_fetch_start_date(start_date: str, warmup_years: int = 1) -> str:
    ...

def load_daily_data_for_feature_research(...):
    ...

def compute_ma_features(df: pd.DataFrame) -> pd.DataFrame:
    ...

def compute_slope_features(df: pd.DataFrame) -> pd.DataFrame:
    ...

def compute_spread_features(df: pd.DataFrame) -> pd.DataFrame:
    ...

def compute_low_dev_features(df: pd.DataFrame) -> pd.DataFrame:
    ...

def compute_high_dev_features(df: pd.DataFrame) -> pd.DataFrame:
    ...

def compute_signed_rolling_percentile(series: pd.Series, history_window: int = 252) -> pd.Series:
    ...

def add_percentile_columns(df: pd.DataFrame) -> pd.DataFrame:
    ...

def save_features_to_csv(df: pd.DataFrame, ticker: str, output_csv_dir: str) -> str:
    ...

def save_features_to_sqlite(df: pd.DataFrame, sqlite_path: str, table_name: str) -> int:
    ...
```

---

## 14. 计算细节强制要求

### 14.1 所有滚动计算都必须右对齐到 `t-1`
也就是：

- `t` 时的 MA / slope / dev / percentile
- 只能用 `t-1` 及更早

### 14.2 不允许未来函数
禁止以下错误做法：

- 直接对 `close` 做 rolling mean 而不先 shift
- 直接用当天 `high` / `low`
- 用包含 `t` 的窗口给 `t` 算百分位

### 14.3 样本不足输出 NaN
包括但不限于：

- MA 窗口不足
- slope 窗口不足
- 分位历史窗口不足
- 正负分开后同号样本为空

---

## 15. 日志与异常要求

脚本应输出清晰日志，至少包括：

- 当前 ticker
- 数据读取区间
- warmup 后实际读取行数
- 最终输出行数
- csv 输出路径
- sqlite 写入结果

对于异常：
- 缺列时报明确错误
- 空数据时报明确错误
- 单个 ticker 出错时建议记录后继续下一个 ticker，但最终汇总报出失败列表

---

## 16. 首版不做的事情

本任务不要做：

- 不要做 Streamlit
- 不要做图表输出
- 不要做状态编码
- 不要做 Markov 分析
- 不要做策略信号
- 不要做回测
- 不要做卖出逻辑
- 不要做 UI

只完成“**数据准备 → 特征计算 → 百分位 → SQLite/CSV 输出**”。

---

## 17. 给 Codex 的明确要求

1. 优先复用 `app/data/` 下已有函数
2. 特征主流程写在 `scripts/compute_trend_features.py`
3. 所有函数必须有 type hints
4. 所有日期处理必须显式、可审计
5. 所有特征在 `t` 时都只能使用 `t-1` 及更早数据
6. 百分位默认历史窗口固定为 252 个交易日
7. 百分位必须正负分开计算，负值保留负号
8. warmup 默认向前扩展 1 个自然年
9. 即使 warmup 后仍不足样本，也必须输出 `NaN`
10. 每个 ticker 单独导出一个 CSV
11. 所有 ticker 合并写入一个 SQLite 文件
12. 代码优先保证正确、可运行、可复查，不必过度抽象

---

## 18. 一句话任务定义

在 `scripts/` 下实现一个趋势研究特征计算脚本：  
**复用 app 数据层，针对多个 ticker 拉取带 warmup 的日线数据，在严格无未来函数的前提下计算 MA、slope、spread、low/high 偏离率及其滚动分位，并将结果输出为一个汇总 SQLite 和多个按 ticker 拆分的 CSV。**

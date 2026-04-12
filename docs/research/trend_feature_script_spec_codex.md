# Codex执行版：趋势/标签特征计算脚本

## 1. 任务目标
在 `scripts/compute_trend_features.py` 中实现一个**研究用特征计算脚本**。

脚本职责仅限：
1. 复用 `app/data/` 现有数据层读取/更新日线数据
2. 对一个或多个 ticker 计算 `hist_*` 与 `fut_*` 特征
3. 计算各特征对应的滚动百分位
4. 输出：
   - 一个汇总 SQLite
   - 每个 ticker 一个独立 CSV

不做：
- 不做交易
- 不做回测
- 不做可视化
- 不做 UI
- 不做策略信号

---

## 2. 文件位置
新增主文件：

```text
scripts/compute_trend_features.py
```

允许少量补充 `app/data/` 辅助函数，但不要在 `scripts/` 里复制数据库逻辑。

---

## 3. 输入参数
脚本至少支持：

```python
tickers: list[str]
start_date: str
end_date: str
daily_db_path: str
output_sqlite_path: str
output_csv_dir: str
use_update: bool
provider_name: str   # 默认 local；必要时允许 yfinance
```

示例：

```python
tickers = ["SPY", "QQQ", "NVDA"]
start_date = "2024-01-01"
end_date = "2026-03-31"
```

---

## 4. 输出要求
### 4.1 SQLite
示例：

```text
data/processed/trend_features.db
```

表名建议：

```text
trend_features_daily
```

唯一键建议：

```text
(ticker, datetime)
```

### 4.2 CSV
每个 ticker 一个文件，例如：

```text
data/processed/features/SPY_trend_features.csv
```

CSV 规则：
- 只保留 `start_date ~ end_date`
- 日期升序
- UTF-8

---

## 5. warmup 规则
为保证 MA / slope / drv / pct 足够历史样本：

```text
fetch_start_date = start_date - 1 calendar year
```

例如：
- 输出起点：`2024-01-01`
- 实际取数起点：`2023-01-01`

样本仍不足时：
- 输出 `NaN`
- 不允许填 0
- 不允许缩窗
- 不允许前值填充

---

## 6. 数据准备流程
对每个 ticker：
1. 计算 `fetch_start_date`
2. `use_update=True` 时，调用 `app/data/updater.py` 更新 `fetch_start_date ~ end_date`
3. 从日线数据库读取 `1d` 数据
4. 标准化并检查：
   - 日期升序
   - 去重
   - 必要列：`datetime/open/high/low/close/volume`
5. 在完整 warmup 数据上计算全部特征
6. 最终裁剪到 `start_date ~ end_date`
7. 保存 CSV
8. 合并所有 ticker 后写入 SQLite

---

## 7. 命名规则
### 7.1 前缀
- `hist_*`：历史可见特征体系
- `fut_*`：未来局部形态体系

### 7.2 窗口缩写
- `w` = 5d
- `m` = 20d
- `q` = 60d
- `h` = 120d

### 7.3 spread 缩写
- `w_m` = 5d / 20d
- `m_q` = 20d / 60d
- `q_h` = 60d / 120d

### 7.4 变化率命名
对某个已生成特征序列再取最近 N 点线性拟合斜率：
- `drv2`
- `drv5`

例：
- `hist_slope_drv2_w`
- `hist_spread_drv5_m_q`
- `fut_low_dev_drv2_m`

---

## 8. 统一时点语义

### 8.1 hist 体系
`hist_*` 表示：

> 在第 t 行这个时点，交易者当时已经能够看到的历史信息。

因此先构造并保存历史参考层：

```text
hist_open(t)  = open[t-1]
hist_high(t)  = high[t-1]
hist_low(t)   = low[t-1]
hist_close(t) = close[t-1]
```

说明：
- 这 4 列需要保存到 CSV / SQLite
- 所有一级 `hist_*` 特征必须直接基于这组 `hist_*` 参考层计算

### 8.2 fut 体系
`fut_*` 表示：

> 以第 t 行为中心观察到的未来局部形态。

窗口定义：

#### fut_w（5d）
```text
[t-2, t-1, t, t+1, t+2]
```

#### fut_m（20d）
```text
[t-10, t-9, ..., t-1, t, ..., t+8, t+9]
```

说明：
- `fut_*` 不表示交易当时可见信息
- 用于未来标签 / 强度 / 局部形态研究

### 8.3 shift 统一规则
- 输入源若为**原始市场数据**，先按对应体系完成时间对齐
- 输入源若为**已经生成好的 `hist_*` / `fut_*` 特征列**，直接使用本行值继续派生，不再重复 shift

核心原则：

> 是否 shift 取决于输入源是原始市场数据还是已定义完成的特征列，而不是取决于当前特征名称。

---

## 9. 一级特征定义

### 9.1 hist 参考层
输出：
- `hist_open`
- `hist_high`
- `hist_low`
- `hist_close`

定义：

```text
hist_open(t)  = open[t-1]
hist_high(t)  = high[t-1]
hist_low(t)   = low[t-1]
hist_close(t) = close[t-1]
```

### 9.2 hist MA
输出：
- `hist_ma_w`
- `hist_ma_m`
- `hist_ma_q`
- `hist_ma_h`

定义：

```text
hist_ma_w(t) = mean(hist_close[t], ..., hist_close[t-4])
hist_ma_m(t) = mean(hist_close[t], ..., hist_close[t-19])
hist_ma_q(t) = mean(hist_close[t], ..., hist_close[t-59])
hist_ma_h(t) = mean(hist_close[t], ..., hist_close[t-119])
```

### 9.3 hist slope
输出：
- `hist_slope_w`
- `hist_slope_m`
- `hist_slope_q`
- `hist_slope_h`

定义：
- 对 `hist_close` 最近 N 点做线性拟合斜率

### 9.4 fut MA
输出：
- `fut_ma_w`
- `fut_ma_m`

定义：

```text
fut_ma_w(t) = mean(close[t-2], close[t-1], close[t], close[t+1], close[t+2])
fut_ma_m(t) = mean(close[t-10], ..., close[t], ..., close[t+9])
```

### 9.5 fut slope
输出：
- `fut_slope_w`
- `fut_slope_m`

定义：
- 对对应中心窗口内 `close` 做线性拟合斜率

### 9.6 hist low_dev / high_dev
输出：
- `hist_low_dev_w/m/q/h`
- `hist_high_dev_w/m/q/h`

定义：

```text
hist_low_dev_w(t)  = hist_low(t)  / hist_ma_w(t) - 1
hist_low_dev_m(t)  = hist_low(t)  / hist_ma_m(t) - 1
hist_low_dev_q(t)  = hist_low(t)  / hist_ma_q(t) - 1
hist_low_dev_h(t)  = hist_low(t)  / hist_ma_h(t) - 1

hist_high_dev_w(t) = hist_high(t) / hist_ma_w(t) - 1
hist_high_dev_m(t) = hist_high(t) / hist_ma_m(t) - 1
hist_high_dev_q(t) = hist_high(t) / hist_ma_q(t) - 1
hist_high_dev_h(t) = hist_high(t) / hist_ma_h(t) - 1
```

### 9.7 fut low_dev / high_dev
输出：
- `fut_low_dev_w`
- `fut_low_dev_m`
- `fut_high_dev_w`
- `fut_high_dev_m`

定义：**分子使用窗口正中心当日 `low[t] / high[t]`**。

```text
fut_low_dev_w(t)  = low[t]  / fut_ma_w(t) - 1
fut_low_dev_m(t)  = low[t]  / fut_ma_m(t) - 1

fut_high_dev_w(t) = high[t] / fut_ma_w(t) - 1
fut_high_dev_m(t) = high[t] / fut_ma_m(t) - 1
```

---

## 10. 二级 / 三级特征定义

### 10.1 spread
#### hist
- `hist_spread_w_m = hist_ma_w / hist_ma_m - 1`
- `hist_spread_m_q = hist_ma_m / hist_ma_q - 1`
- `hist_spread_q_h = hist_ma_q / hist_ma_h - 1`

#### fut
- `fut_spread_w_m = fut_ma_w / fut_ma_m - 1`

### 10.2 通用 drv2 / drv5
对任一已生成特征序列 `X(t)`：
- `X_drv2(t)`：最近 2 点线性拟合斜率
- `X_drv5(t)`：最近 5 点线性拟合斜率

### 10.3 low_dev / high_dev 的 slope
定义：
- 对 `*_dev_w` 取最近 5 点斜率
- 对 `*_dev_m` 取最近 20 点斜率
- 对 `*_dev_q` 取最近 60 点斜率
- 对 `*_dev_h` 取最近 120 点斜率

输出：
- `hist_low_dev_slope_w/m/q/h`
- `hist_high_dev_slope_w/m/q/h`
- `fut_low_dev_slope_w/m`
- `fut_high_dev_slope_w/m`

### 10.4 全量派生特征必须覆盖
#### hist
- `hist_slope_drv2/5_w/m/q/h`
- `hist_spread_w_m/m_q/q_h`
- `hist_spread_drv2/5_w_m/m_q/q_h`
- `hist_low_dev_drv2/5_w/m/q/h`
- `hist_high_dev_drv2/5_w/m/q/h`
- `hist_low_dev_slope_w/m/q/h`
- `hist_high_dev_slope_w/m/q/h`
- `hist_low_dev_slope_drv2/5_w/m/q/h`
- `hist_high_dev_slope_drv2/5_w/m/q/h`

#### fut
- `fut_slope_drv2/5_w/m`
- `fut_spread_w_m`
- `fut_spread_drv2/5_w_m`
- `fut_low_dev_drv2/5_w/m`
- `fut_high_dev_drv2/5_w/m`
- `fut_low_dev_slope_w/m`
- `fut_high_dev_slope_w/m`
- `fut_low_dev_slope_drv2/5_w/m`
- `fut_high_dev_slope_drv2/5_w/m`

---

## 11. 百分位规则
实现通用函数，例如：

```python
def compute_signed_rolling_percentile(series: pd.Series, history_window: int = 252) -> pd.Series:
    ...
```

规则：
- 历史比较集合只取 `t-1 ... t-history_window`
- 不包含 `t`
- `x_t > 0`：在历史正值子集里计算 `<= x_t` 的比例
- `x_t < 0`：在历史负值子集绝对值里计算 `<= |x_t|` 的比例，再乘 `-1`
- `x_t == 0`：输出 `0`
- 历史不足或同号子集为空：输出 `NaN`

适用范围：
- 对所有已生成完成的 `hist_*` 特征
- 对所有已生成完成的 `fut_*` 特征

备注：
- `hist_pct`：历史可见特征在过去同类历史中的相对位置
- `fut_pct`：当前样本对应未来局部形态，在历史同类未来形态中的相对位置

---

## 12. 最终输出字段（分组）

### 12.1 基础列
- `datetime, ticker, open, high, low, close, volume`

### 12.2 hist 参考层
- `hist_open, hist_high, hist_low, hist_close`

### 12.3 hist 一级
- `hist_ma_w/m/q/h`
- `hist_slope_w/m/q/h`
- `hist_low_dev_w/m/q/h`
- `hist_high_dev_w/m/q/h`

### 12.4 hist 派生
- `hist_spread_w_m/m_q/q_h`
- `hist_slope_drv2/5_w/m/q/h`
- `hist_spread_drv2/5_w_m/m_q/q_h`
- `hist_low_dev_drv2/5_w/m/q/h`
- `hist_high_dev_drv2/5_w/m/q/h`
- `hist_low_dev_slope_w/m/q/h`
- `hist_high_dev_slope_w/m/q/h`
- `hist_low_dev_slope_drv2/5_w/m/q/h`
- `hist_high_dev_slope_drv2/5_w/m/q/h`

### 12.5 hist 百分位
对以下全部生成对应 `*_pct_*`：
- `hist_slope_*`
- `hist_slope_drv2/5_*`
- `hist_spread_*`
- `hist_spread_drv2/5_*`
- `hist_low_dev_*`
- `hist_low_dev_drv2/5_*`
- `hist_high_dev_*`
- `hist_high_dev_drv2/5_*`
- `hist_low_dev_slope_*`
- `hist_low_dev_slope_drv2/5_*`
- `hist_high_dev_slope_*`
- `hist_high_dev_slope_drv2/5_*`

### 12.6 fut 一级
- `fut_ma_w/m`
- `fut_slope_w/m`
- `fut_low_dev_w/m`
- `fut_high_dev_w/m`

### 12.7 fut 派生
- `fut_spread_w_m`
- `fut_slope_drv2/5_w/m`
- `fut_spread_drv2/5_w_m`
- `fut_low_dev_drv2/5_w/m`
- `fut_high_dev_drv2/5_w/m`
- `fut_low_dev_slope_w/m`
- `fut_high_dev_slope_w/m`
- `fut_low_dev_slope_drv2/5_w/m`
- `fut_high_dev_slope_drv2/5_w/m`

### 12.8 fut 百分位
对以下全部生成对应 `*_pct_*`：
- `fut_slope_*`
- `fut_slope_drv2/5_*`
- `fut_spread_*`
- `fut_spread_drv2/5_*`
- `fut_low_dev_*`
- `fut_low_dev_drv2/5_*`
- `fut_high_dev_*`
- `fut_high_dev_drv2/5_*`
- `fut_low_dev_slope_*`
- `fut_low_dev_slope_drv2/5_*`
- `fut_high_dev_slope_*`
- `fut_high_dev_slope_drv2/5_*`

---

## 13. 建议函数结构

```python
def compute_fetch_start_date(start_date: str, warmup_years: int = 1) -> str:
    ...

def load_daily_data_for_feature_research(...):
    ...

def build_hist_reference_columns(df: pd.DataFrame) -> pd.DataFrame:
    ...

def compute_hist_ma_features(df: pd.DataFrame) -> pd.DataFrame:
    ...

def compute_hist_slope_features(df: pd.DataFrame) -> pd.DataFrame:
    ...

def compute_hist_dev_features(df: pd.DataFrame) -> pd.DataFrame:
    ...

def compute_hist_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    ...

def compute_fut_core_features(df: pd.DataFrame) -> pd.DataFrame:
    ...

def compute_fut_derived_features(df: pd.DataFrame) -> pd.DataFrame:
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

## 14. 实现硬约束
1. 优先复用 `app/data/` 现有能力
2. 主流程必须放在 `scripts/compute_trend_features.py`
3. 所有函数必须有 type hints
4. 所有滚动计算必须显式、可审计
5. 所有样本不足位置输出 `NaN`
6. 百分位固定用 `252` 历史窗口
7. 百分位必须正负分开，负值保留负号
8. `hist_*` 与 `fut_*` 必须严格按本文件语义实现，不可混用
9. 每个 ticker 单独导出一个 CSV
10. 全部 ticker 合并写入一个 SQLite
11. 优先保证正确、可运行、可复查，不必过度抽象

---

## 15. Codex执行顺序
1. 先搭好数据读取/更新/保存主流程
2. 先实现 `hist_*` 参考层与一级特征
3. 再实现 `hist_*` 二级/三级特征
4. 再实现 `fut_*` 一级特征
5. 再实现 `fut_*` 二级/三级特征
6. 最后统一加全部百分位列
7. 输出 CSV 与 SQLite
8. 用 `SPY` 做首轮验证

---

## 16. 一句话任务定义
实现一个研究用日线特征计算脚本：
**复用 app 数据层，对多个 ticker 计算 `hist_*` 历史可见特征与 `fut_*` 未来局部形态特征（含全量派生与百分位），并输出到一个汇总 SQLite 和多个按 ticker 拆分的 CSV。**

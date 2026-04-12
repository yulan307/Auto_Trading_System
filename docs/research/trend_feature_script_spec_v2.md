# 特征值计算脚本开发文档（修订版，供 Codex 实现）

## 1. 文档目标

本文件用于驱动 Codex 在 `scripts/` 下实现一个**趋势研究 / 标签研究用特征值计算脚本**。  
该脚本不负责交易、不负责回测、不负责可视化，只负责：

1. 复用 `app/` 下已有的数据获取 / 数据更新 / 数据读取相关函数
2. 针对一个或多个 ticker 拉取并准备日线数据
3. 计算 `hist_*` 历史特征体系
4. 计算 `fut_*` 未来局部形态体系
5. 计算对应百分位
6. 将结果同时保存为：
   - 一个汇总 SQLite 文件（包含全部 ticker）
   - 每个 ticker 一个独立 CSV 文件

本脚本定位为**研究工具**，用于后续趋势模块、状态编码、分位系统研究，以及未来标签 / 强度研究，不直接写入正式策略模块。

---

## 2. 实现位置

建议新增以下文件：

```text
scripts/compute_trend_features.py
```

如有必要，可在 `app/` 下补充少量可复用函数，但**本次的特征计算主流程应放在 `scripts/` 下**，避免在策略 / 标签尚未定型前过早沉入正式模块。

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

### 3.3 统一时点语义
本脚本统一采用两套不同但各自内部一致的时点语义：

- `hist_*`：**本行时点可见的历史信息**
- `fut_*`：**以本行为中心构造的未来局部形态信息**

两套体系允许使用相同的公式结构，但**时间语义不同，不能混用解释**。

### 3.4 样本不足输出 NaN
若 warmup 后数据仍不足以支撑某项计算，必须输出 `NaN`，不得用 0、前值填充、或强行缩窗。

### 3.5 多 ticker 支持
允许输入多个 ticker。  
输出规则：

- SQLite：一个文件，包含所有 ticker 的结果
- CSV：每个 ticker 单独一个文件

---

## 4. 输入与输出要求

### 4.1 输入参数

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

### 4.2 输出文件

#### 4.2.1 SQLite
输出一个汇总 sqlite 文件，例如：

```text
data/processed/trend_features.db
```

要求包含所有 ticker 的结果表，例如：

- 表名：`trend_features_daily`

#### 4.2.2 CSV
每个 ticker 一个独立 csv 文件，例如：

```text
data/processed/features/SPY_trend_features.csv
data/processed/features/QQQ_trend_features.csv
data/processed/features/NVDA_trend_features.csv
```

---

## 5. Warmup 数据范围要求

为了保证 MA、slope、各类导数、百分位有足够历史，脚本在拉取或读取数据时，不能只取用户输入的 `start_date ~ end_date`。

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

## 7. 命名体系

### 7.1 总前缀

为区分历史特征与未来标签 / 未来形态，统一使用：

- `hist_*`：历史体系
- `fut_*`：未来局部形态体系

### 7.2 时间尺度压缩命名

将 5 / 20 / 60 / 120 日窗口压缩为：

- `w` = 5d = 1 week
- `m` = 20d = 1 month
- `q` = 60d = 1 quarter
- `h` = 120d = half year

### 7.3 spread 配对命名

- `w_m` = 5d / 20d
- `m_q` = 20d / 60d
- `q_h` = 60d / 120d

### 7.4 变化率命名

对已经生成好的某条特征序列，再取最近 N 点做线性拟合斜率，统一命名为：

- `drv2`：最近 2 点斜率
- `drv5`：最近 5 点斜率

例如：

- `hist_slope_drv2_w`
- `hist_spread_drv5_m_q`
- `fut_low_dev_drv2_m`

---

## 8. 统一时点语义与分层规则

### 8.1 hist 体系

`hist_*` 统一表示：

> 在第 `t` 行这个时点，交易者当时已经能够看到的历史信息。

为保证语义统一，先构造并保存**历史参考层**：

```text
hist_open(t)  = open[t-1]
hist_high(t)  = high[t-1]
hist_low(t)   = low[t-1]
hist_close(t) = close[t-1]
```

说明：
- 这层允许保存到 CSV / SQLite
- 它不是派生特征，而是“历史对齐后的参考数据层”
- 所有一级 `hist_*` 特征都必须直接基于这组参考层计算

### 8.2 fut 体系

`fut_*` 统一表示：

> 以第 `t` 行为中心观察到的未来局部形态。

`fut_*` 的窗口定义如下：

#### `fut_w`（5d）
以 `t` 为中心：

```text
[t-2, t-1, t, t+1, t+2]
```

#### `fut_m`（20d）
以 `t` 为准中心，固定约定为：

```text
[t-10, t-9, ..., t-1, t, ..., t+8, t+9]
```

共 20 个点。

说明：
- 由于 20 为偶数，不存在完全对称中心，因此固定采用上面的准对称定义
- `fut_*` 不表示交易当时可见的信息，而是用于未来标签 / 局部形态研究

### 8.3 分层计算规则

#### 第 0 层：原始市场数据层
- `open`
- `high`
- `low`
- `close`
- `volume`

#### 第 1 层：参考层
- `hist_open`
- `hist_high`
- `hist_low`
- `hist_close`

#### 第 2 层：一级特征
直接基于参考层或中心窗口原始数据得到：
- `*_ma_*`
- `*_slope_*`
- `*_low_dev_*`
- `*_high_dev_*`

#### 第 3 层：二级特征
基于已经生成好的本行特征继续计算：
- `*_spread_*`
- `*_slope_drv2/5_*`
- `*_low_dev_drv2/5_*`
- `*_high_dev_drv2/5_*`
- `*_low_dev_slope_*`
- `*_high_dev_slope_*`

#### 第 4 层：三级特征
继续基于二级特征派生：
- `*_spread_drv2/5_*`
- `*_low_dev_slope_drv2/5_*`
- `*_high_dev_slope_drv2/5_*`

#### 百分位层
对任意已经定义完成的 `hist_*` 或 `fut_*` 特征列，再按统一规则计算 `*_pct_*`。

### 8.4 shift 规则统一口径

- 若输入源是**原始市场数据**，则必须先按对应体系完成时间对齐
- 若输入源是**已经定义完成的 `hist_*` / `fut_*` 特征列**，则直接使用这些列的本行值继续派生，不再重复 shift

也就是说：

> 是否需要 shift，不取决于正在计算的特征名称，而取决于输入源是“原始市场数据”还是“已定义完成的特征列”。

---

## 9. 一级特征定义

### 9.1 hist 历史参考层

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
hist_ma_w(t) = mean(hist_close[t], hist_close[t-1], ..., hist_close[t-4])
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
对 `hist_close` 的最近 N 点做线性拟合斜率。

例如：

```text
hist_slope_w(t) = slope of [hist_close[t-4], ..., hist_close[t]]
```

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
对中心窗口内 `close` 做线性拟合斜率。

### 9.6 hist low_dev / high_dev

输出：
- `hist_low_dev_w`
- `hist_low_dev_m`
- `hist_low_dev_q`
- `hist_low_dev_h`
- `hist_high_dev_w`
- `hist_high_dev_m`
- `hist_high_dev_q`
- `hist_high_dev_h`

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

定义：
**使用窗口正中心当日的 `low[t]` / `high[t]` 作为分子。**

```text
fut_low_dev_w(t)  = low[t]  / fut_ma_w(t) - 1
fut_low_dev_m(t)  = low[t]  / fut_ma_m(t) - 1

fut_high_dev_w(t) = high[t] / fut_ma_w(t) - 1
fut_high_dev_m(t) = high[t] / fut_ma_m(t) - 1
```

说明：
- `fut` 的 `low_dev/high_dev` 不使用窗口内极值
- 明确使用正中心当日的 `low/high`
- 其含义是：当前这一天在“以当前为中心的局部价格结构”中的偏离程度

---

## 10. 二级 / 三级特征定义

### 10.1 spread

#### hist spread
输出：
- `hist_spread_w_m`
- `hist_spread_m_q`
- `hist_spread_q_h`

定义：

```text
hist_spread_w_m(t) = hist_ma_w(t) / hist_ma_m(t) - 1
hist_spread_m_q(t) = hist_ma_m(t) / hist_ma_q(t) - 1
hist_spread_q_h(t) = hist_ma_q(t) / hist_ma_h(t) - 1
```

#### fut spread
输出：
- `fut_spread_w_m`

定义：

```text
fut_spread_w_m(t) = fut_ma_w(t) / fut_ma_m(t) - 1
```

### 10.2 各类 drv2 / drv5

统一定义：
对某条已经生成好的特征序列 `X(t)`，其：

- `X_drv2(t)`：用最近 2 个点做线性拟合斜率
- `X_drv5(t)`：用最近 5 个点做线性拟合斜率

说明：
- 这里的输入 `X` 已经是同一体系下定义完成的特征列
- 因此直接使用 `X` 本行值及其历史序列

### 10.3 low_dev / high_dev 的 slope

统一定义：
对 `low_dev` 或 `high_dev` 这条特征序列，分别再取对应主窗口长度做线性拟合斜率。

#### hist
输出：
- `hist_low_dev_slope_w`
- `hist_low_dev_slope_m`
- `hist_low_dev_slope_q`
- `hist_low_dev_slope_h`
- `hist_high_dev_slope_w`
- `hist_high_dev_slope_m`
- `hist_high_dev_slope_q`
- `hist_high_dev_slope_h`

#### fut
输出：
- `fut_low_dev_slope_w`
- `fut_low_dev_slope_m`
- `fut_high_dev_slope_w`
- `fut_high_dev_slope_m`

说明：
- `*_dev_slope_w`：对对应 `*_dev_w` 序列取最近 5 点线性拟合斜率
- `*_dev_slope_m`：对对应 `*_dev_m` 序列取最近 20 点线性拟合斜率
- `*_dev_slope_q`：对对应 `*_dev_q` 序列取最近 60 点线性拟合斜率
- `*_dev_slope_h`：对对应 `*_dev_h` 序列取最近 120 点线性拟合斜率

### 10.4 spread 的变化率

#### hist
输出：
- `hist_spread_drv2_w_m`
- `hist_spread_drv2_m_q`
- `hist_spread_drv2_q_h`
- `hist_spread_drv5_w_m`
- `hist_spread_drv5_m_q`
- `hist_spread_drv5_q_h`

#### fut
输出：
- `fut_spread_drv2_w_m`
- `fut_spread_drv5_w_m`

### 10.5 low_dev / high_dev 本体变化率

#### hist
输出：
- `hist_low_dev_drv2_w`
- `hist_low_dev_drv2_m`
- `hist_low_dev_drv2_q`
- `hist_low_dev_drv2_h`
- `hist_low_dev_drv5_w`
- `hist_low_dev_drv5_m`
- `hist_low_dev_drv5_q`
- `hist_low_dev_drv5_h`
- `hist_high_dev_drv2_w`
- `hist_high_dev_drv2_m`
- `hist_high_dev_drv2_q`
- `hist_high_dev_drv2_h`
- `hist_high_dev_drv5_w`
- `hist_high_dev_drv5_m`
- `hist_high_dev_drv5_q`
- `hist_high_dev_drv5_h`

#### fut
输出：
- `fut_low_dev_drv2_w`
- `fut_low_dev_drv2_m`
- `fut_low_dev_drv5_w`
- `fut_low_dev_drv5_m`
- `fut_high_dev_drv2_w`
- `fut_high_dev_drv2_m`
- `fut_high_dev_drv5_w`
- `fut_high_dev_drv5_m`

### 10.6 low_dev_slope / high_dev_slope 的变化率

#### hist
输出：
- `hist_low_dev_slope_drv2_w`
- `hist_low_dev_slope_drv2_m`
- `hist_low_dev_slope_drv2_q`
- `hist_low_dev_slope_drv2_h`
- `hist_low_dev_slope_drv5_w`
- `hist_low_dev_slope_drv5_m`
- `hist_low_dev_slope_drv5_q`
- `hist_low_dev_slope_drv5_h`
- `hist_high_dev_slope_drv2_w`
- `hist_high_dev_slope_drv2_m`
- `hist_high_dev_slope_drv2_q`
- `hist_high_dev_slope_drv2_h`
- `hist_high_dev_slope_drv5_w`
- `hist_high_dev_slope_drv5_m`
- `hist_high_dev_slope_drv5_q`
- `hist_high_dev_slope_drv5_h`

#### fut
输出：
- `fut_low_dev_slope_drv2_w`
- `fut_low_dev_slope_drv2_m`
- `fut_low_dev_slope_drv5_w`
- `fut_low_dev_slope_drv5_m`
- `fut_high_dev_slope_drv2_w`
- `fut_high_dev_slope_drv2_m`
- `fut_high_dev_slope_drv5_w`
- `fut_high_dev_slope_drv5_m`

---

## 11. 百分位计算统一规范

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

### 适用范围

对所有已生成完成的：
- `hist_*`
- `fut_*`

特征均按同一套规则计算对应 `*_pct_*` 列。

说明：
- `hist_pct` 表示历史可见特征在过去同类历史中的相对位置
- `fut_pct` 表示当前样本对应的未来局部形态特征，在历史全部样本的同类未来形态中的相对位置

---

## 12. 建议输出字段清单

### 12.1 基础标识列
- `datetime`
- `ticker`
- `open`
- `high`
- `low`
- `close`
- `volume`

### 12.2 hist 历史参考层
- `hist_open`
- `hist_high`
- `hist_low`
- `hist_close`

### 12.3 hist 一级特征
- `hist_ma_w`
- `hist_ma_m`
- `hist_ma_q`
- `hist_ma_h`
- `hist_slope_w`
- `hist_slope_m`
- `hist_slope_q`
- `hist_slope_h`
- `hist_low_dev_w`
- `hist_low_dev_m`
- `hist_low_dev_q`
- `hist_low_dev_h`
- `hist_high_dev_w`
- `hist_high_dev_m`
- `hist_high_dev_q`
- `hist_high_dev_h`

### 12.4 hist 二级 / 三级特征
- `hist_spread_w_m`
- `hist_spread_m_q`
- `hist_spread_q_h`
- `hist_slope_drv2_w`
- `hist_slope_drv2_m`
- `hist_slope_drv2_q`
- `hist_slope_drv2_h`
- `hist_slope_drv5_w`
- `hist_slope_drv5_m`
- `hist_slope_drv5_q`
- `hist_slope_drv5_h`
- `hist_spread_drv2_w_m`
- `hist_spread_drv2_m_q`
- `hist_spread_drv2_q_h`
- `hist_spread_drv5_w_m`
- `hist_spread_drv5_m_q`
- `hist_spread_drv5_q_h`
- `hist_low_dev_drv2_w`
- `hist_low_dev_drv2_m`
- `hist_low_dev_drv2_q`
- `hist_low_dev_drv2_h`
- `hist_low_dev_drv5_w`
- `hist_low_dev_drv5_m`
- `hist_low_dev_drv5_q`
- `hist_low_dev_drv5_h`
- `hist_high_dev_drv2_w`
- `hist_high_dev_drv2_m`
- `hist_high_dev_drv2_q`
- `hist_high_dev_drv2_h`
- `hist_high_dev_drv5_w`
- `hist_high_dev_drv5_m`
- `hist_high_dev_drv5_q`
- `hist_high_dev_drv5_h`
- `hist_low_dev_slope_w`
- `hist_low_dev_slope_m`
- `hist_low_dev_slope_q`
- `hist_low_dev_slope_h`
- `hist_high_dev_slope_w`
- `hist_high_dev_slope_m`
- `hist_high_dev_slope_q`
- `hist_high_dev_slope_h`
- `hist_low_dev_slope_drv2_w`
- `hist_low_dev_slope_drv2_m`
- `hist_low_dev_slope_drv2_q`
- `hist_low_dev_slope_drv2_h`
- `hist_low_dev_slope_drv5_w`
- `hist_low_dev_slope_drv5_m`
- `hist_low_dev_slope_drv5_q`
- `hist_low_dev_slope_drv5_h`
- `hist_high_dev_slope_drv2_w`
- `hist_high_dev_slope_drv2_m`
- `hist_high_dev_slope_drv2_q`
- `hist_high_dev_slope_drv2_h`
- `hist_high_dev_slope_drv5_w`
- `hist_high_dev_slope_drv5_m`
- `hist_high_dev_slope_drv5_q`
- `hist_high_dev_slope_drv5_h`

### 12.5 hist 百分位列
对下列全部 `hist_*` 特征计算对应 `*_pct_*`：
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

### 12.6 fut 一级特征
- `fut_ma_w`
- `fut_ma_m`
- `fut_slope_w`
- `fut_slope_m`
- `fut_low_dev_w`
- `fut_low_dev_m`
- `fut_high_dev_w`
- `fut_high_dev_m`

### 12.7 fut 二级 / 三级特征
- `fut_spread_w_m`
- `fut_slope_drv2_w`
- `fut_slope_drv2_m`
- `fut_slope_drv5_w`
- `fut_slope_drv5_m`
- `fut_spread_drv2_w_m`
- `fut_spread_drv5_w_m`
- `fut_low_dev_drv2_w`
- `fut_low_dev_drv2_m`
- `fut_low_dev_drv5_w`
- `fut_low_dev_drv5_m`
- `fut_high_dev_drv2_w`
- `fut_high_dev_drv2_m`
- `fut_high_dev_drv5_w`
- `fut_high_dev_drv5_m`
- `fut_low_dev_slope_w`
- `fut_low_dev_slope_m`
- `fut_high_dev_slope_w`
- `fut_high_dev_slope_m`
- `fut_low_dev_slope_drv2_w`
- `fut_low_dev_slope_drv2_m`
- `fut_low_dev_slope_drv5_w`
- `fut_low_dev_slope_drv5_m`
- `fut_high_dev_slope_drv2_w`
- `fut_high_dev_slope_drv2_m`
- `fut_high_dev_slope_drv5_w`
- `fut_high_dev_slope_drv5_m`

### 12.8 fut 百分位列
对下列全部 `fut_*` 特征计算对应 `*_pct_*`：
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

## 13. SQLite 保存要求

### 13.1 文件
输出一个 sqlite 文件，例如：

```text
data/processed/trend_features.db
```

### 13.2 表名
建议表名：

```text
trend_features_daily
```

### 13.3 主键建议
建议将以下组合作为唯一键：

```text
(ticker, datetime)
```

### 13.4 保存规则
- 所有 ticker 结果写入同一张表
- 允许覆盖同一 `(ticker, datetime)` 的旧结果
- 写入前保证 `datetime` 标准化
- 写入后应可按 ticker 查询

---

## 14. CSV 保存要求

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

## 15. 建议脚本结构

```python
def main():
    # 1. 解析输入参数
    # 2. 计算 fetch_start_date
    # 3. 对每个 ticker 执行：
    #    a. update data（可选）
    #    b. load data
    #    c. build hist reference layer
    #    d. compute hist features
    #    e. compute fut features
    #    f. add percentile columns
    #    g. clip to output range
    #    h. save per-ticker csv
    # 4. merge all ticker results
    # 5. save sqlite
```

建议拆分函数：

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

## 16. 计算细节强制要求

1. 所有 `hist_*` 一级特征都必须基于 `hist_open/high/low/close` 参考层构造。
2. 所有 `fut_*` 一级特征都必须严格按中心窗口定义构造。
3. `fut_low_dev_*` / `fut_high_dev_*` 必须使用中心日 `low[t]` / `high[t]` 作为分子。
4. 所有二级 / 三级特征必须直接基于已定义完成的同体系本行特征继续计算，不得重复做额外 shift。
5. 所有百分位列统一使用过去 252 个交易日的历史样本，不包含当前行。
6. 正负分开计算，负值保留负号。
7. 样本不足一律输出 `NaN`。

---

## 17. 日志与异常要求

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

## 18. 首版不做的事情

本任务不要做：
- 不要做 Streamlit
- 不要做图表输出
- 不要做状态编码
- 不要做 Markov 分析
- 不要做策略信号
- 不要做回测
- 不要做卖出逻辑
- 不要做 UI

只完成“**数据准备 → hist/fut 特征计算 → 百分位 → SQLite/CSV 输出**”。

---

## 19. 给 Codex 的明确要求

1. 优先复用 `app/data/` 下已有函数
2. 特征主流程写在 `scripts/compute_trend_features.py`
3. 所有函数必须有 type hints
4. 所有日期处理必须显式、可审计
5. `hist_*` 与 `fut_*` 必须严格按本文档的时间语义分开实现
6. 百分位默认历史窗口固定为 252 个交易日
7. 百分位必须正负分开计算，负值保留负号
8. warmup 默认向前扩展 1 个自然年
9. 即使 warmup 后仍不足样本，也必须输出 `NaN`
10. 每个 ticker 单独导出一个 CSV
11. 所有 ticker 合并写入一个 SQLite 文件
12. 代码优先保证正确、可运行、可复查，不必过度抽象

---

## 20. 一句话任务定义

在 `scripts/` 下实现一个趋势研究 / 标签研究特征计算脚本：  
**复用 app 数据层，针对多个 ticker 拉取带 warmup 的日线数据，在统一时点语义下同时计算 `hist_*` 历史特征体系与 `fut_*` 未来局部形态体系，包括 MA、slope、spread、low/high 偏离率、各类 slope / drv2 / drv5 及其滚动百分位，并将结果输出为一个汇总 SQLite 和多个按 ticker 拆分的 CSV。**

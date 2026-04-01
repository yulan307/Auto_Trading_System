# 多标的趋势区间与反弹信号研究输出规范（Codex 可直接推进）

## 1. 文档目标

本文件用于驱动代码实现一个**多 ticker 回测研究脚本**，目标不是直接生成交易策略，而是：

1. 对多个 ticker 在指定时间段内批量计算标准趋势特征。
2. 在标准特征基础上，新增本轮讨论得到的三个核心结构变量：
   - `slope60`
   - `spread2060`
   - `d_spread2060`
3. 将三者的正负号组合拆分为 **8 种结构状态**，暂不做语义命名，只输出符号组合。
4. 计算“反弹点信号”所需的基础信号，但暂不做最终交易决策。
5. 输出逐日明细 CSV，便于后续跨 ticker 统计、筛选、回测与人工验证。

本阶段的目标是**先完整输出研究数据**，而不是提前固化买入规则。

---

## 2. 任务边界

### 本阶段要做

- 支持多个 ticker 批量运行。
- 支持自定义开始与结束日期。
- 读取/更新 1d 数据。
- 计算标准特征。
- 计算结构区间符号组合。
- 计算反弹点研究所需基础信号。
- 输出逐日结果表。
- 输出按 ticker 汇总的基础统计表。

### 本阶段不要做

- 不做自动下单。
- 不做 15m 日内追踪。
- 不做最终买卖点分类器。
- 不做区间语义命名。
- 不做 UI。
- 不做复杂参数搜索框架。

---

## 3. 输入与输出

### 3.1 输入

脚本必须支持以下输入：

- `tickers`: 多个 ticker 列表，例如 `SPY, QQQ, IWM, NVDA`
- `start_date`: 回测起始日期
- `end_date`: 回测结束日期
- `interval`: 固定为 `1d`
- `data_source`: 首版支持 `local`，必要时允许先调用已有更新逻辑补齐数据库
- `output_dir`: 输出目录

### 3.2 输出文件

至少输出以下两个文件：

#### 文件 1：逐日明细表
命名建议：

```text
trend_zone_rebound_daily.csv
```

用途：
- 保存每个 ticker、每个交易日的全部特征与符号组合
- 作为后续统计、筛选、研究的基础文件

#### 文件 2：按 ticker 汇总统计表
命名建议：

```text
trend_zone_rebound_summary.csv
```

用途：
- 输出每个 ticker 在回测时间段内各符号组合出现次数
- 统计反弹基础信号出现次数
- 便于横向比较不同 ticker

如后续方便，也可额外输出：

#### 文件 3：组合统计表（可选）
```text
trend_zone_combo_stats.csv
```

用途：
- 跨 ticker 汇总 8 种符号组合的出现次数与占比

---

## 4. 数据依赖

优先复用当前项目中已有的：

- 本地 daily 数据库读取逻辑
- 数据更新逻辑（若本地数据不足则补齐）
- trend module 中已有 MA 计算逻辑

如果已有函数可直接复用，则不要重复实现相同功能。

建议复用的已有能力：

1. `load daily bars`
2. `update db if data missing`
3. `compute ma5/20/60`
4. `compute slope5/20/60`
5. `compute state/day_state if已有`

---

## 5. 标准特征输出要求

逐日明细表中，除原始 OHLCV 外，至少必须输出以下标准特征。

### 5.1 原始字段

- `ticker`
- `date`
- `open`
- `high`
- `low`
- `close`
- `volume`

### 5.2 标准均线字段

- `ma5`
- `ma20`
- `ma60`

### 5.3 标准斜率字段

斜率定义沿用当前项目中 trend 模块已有定义。若当前项目已有统一实现，必须直接复用。

至少输出：

- `slope5`
- `slope20`
- `slope60`

### 5.4 标准结构编码字段

若已有实现，必须一并输出：

- `ma_order_code`
- `slope_code`
- `day_state_code`
- `state_seq_5d`

若某字段当前项目尚未统一，则可先保留为空，但优先复用已有实现。

---

## 6. 新增研究字段：区间结构相关

### 6.1 spread2060

定义：

```text
spread2060(t) = (ma20(t) - ma60(t)) / ma60(t)
```

输出列名：

- `spread2060`

### 6.2 d_spread2060

定义：

```text
d_spread2060(t) = spread2060(t) - spread2060(t-1)
```

输出列名：

- `d_spread2060`

### 6.3 slope60_sign

根据 `slope60` 正负输出符号：

- `+`：`slope60 > 0`
- `-`：`slope60 < 0`
- `0`：`slope60 == 0`

输出列名：

- `slope60_sign`

### 6.4 spread2060_sign

根据 `spread2060` 正负输出符号：

- `+`：`spread2060 > 0`
- `-`：`spread2060 < 0`
- `0`：`spread2060 == 0`

输出列名：

- `spread2060_sign`

### 6.5 d_spread2060_sign

根据 `d_spread2060` 正负输出符号：

- `+`：`d_spread2060 > 0`
- `-`：`d_spread2060 < 0`
- `0`：`d_spread2060 == 0`

输出列名：

- `d_spread2060_sign`

### 6.6 三因子符号组合

将以下三者按固定顺序拼接：

1. `slope60_sign`
2. `spread2060_sign`
3. `d_spread2060_sign`

例如：

- `+++`
- `++-`
- `+-+`
- `+--`
- `-++`
- `-+-`
- `--+`
- `---`

输出列名：

- `zone_combo_3`

如出现 `0`，保留原样输出，但在 summary 中单独统计，不并入 8 类主组合。

---

## 7. 新增研究字段：反弹点基础信号

本阶段仅输出“反弹点研究所需的基础信号”，不输出最终买点结论。

### 7.1 dev_low5

定义：

```text
dev_low5(t) = low(t) / ma5(t) - 1
```

输出列名：

- `dev_low5`

### 7.2 d_dev_low5

定义：

```text
d_dev_low5(t) = dev_low5(t) - dev_low5(t-1)
```

输出列名：

- `d_dev_low5`

### 7.3 dev_low20

定义：

```text
dev_low20(t) = low(t) / ma20(t) - 1
```

输出列名：

- `dev_low20`

### 7.4 dev_low60

定义：

```text
dev_low60(t) = low(t) / ma60(t) - 1
```

输出列名：

- `dev_low60`

### 7.5 反弹基础信号符号

#### dev_low5_sign

- `+`：`dev_low5 > 0`
- `-`：`dev_low5 < 0`
- `0`：`dev_low5 == 0`

#### d_dev_low5_sign

- `+`：`d_dev_low5 > 0`
- `-`：`d_dev_low5 < 0`
- `0`：`d_dev_low5 == 0`

输出列名：

- `dev_low5_sign`
- `d_dev_low5_sign`

### 7.6 反弹基础组合

将以下两者拼接：

1. `dev_low5_sign`
2. `d_dev_low5_sign`

例如：

- `++`
- `+-`
- `-+`
- `--`

输出列名：

- `rebound_base_combo_2`

当前重点观察组合之一是 `-+`，但本阶段只输出组合，不固化命名，不固化买入规则。

---

## 8. 建议补充输出字段

### 8.1 收盘偏离度

- `dev_close5 = close / ma5 - 1`
- `dev_close20 = close / ma20 - 1`
- `dev_close60 = close / ma60 - 1`

### 8.2 日收益与振幅

- `day_ret = close / close(t-1) - 1`
- `range_pct = (high - low) / close(t-1)`

### 8.3 成交量相对强度

- `vol_ma20`
- `vol_ratio20 = volume / vol_ma20`

### 8.4 未来收益（离线统计用）

- `fwd_ret_1d = close(t+1)/close(t)-1`
- `fwd_ret_3d = close(t+3)/close(t)-1`
- `fwd_ret_5d = close(t+5)/close(t)-1`
- `fwd_ret_10d = close(t+10)/close(t)-1`
- `fwd_ret_20d = close(t+20)/close(t)-1`

这些字段仅作为研究输出，不能用于实时信号。

---

## 9. 逐日明细表字段清单

`trend_zone_rebound_daily.csv` 至少包含以下列：

```text
ticker
date
open
high
low
close
volume
ma5
ma20
ma60
slope5
slope20
slope60
ma_order_code
slope_code
day_state_code
state_seq_5d
spread2060
d_spread2060
slope60_sign
spread2060_sign
d_spread2060_sign
zone_combo_3
dev_low5
d_dev_low5
dev_low20
dev_low60
dev_low5_sign
d_dev_low5_sign
rebound_base_combo_2
dev_close5
dev_close20
dev_close60
day_ret
range_pct
vol_ma20
vol_ratio20
fwd_ret_1d
fwd_ret_3d
fwd_ret_5d
fwd_ret_10d
fwd_ret_20d
valid_row_flag
```

---

## 10. 汇总统计表要求

`trend_zone_rebound_summary.csv` 至少按 `ticker` 输出以下内容：

- `ticker`
- `start_date`
- `end_date`
- `row_count`
- `valid_row_count`
- `combo_+++_count`
- `combo_++-_count`
- `combo_+-+_count`
- `combo_+--_count`
- `combo_-++_count`
- `combo_-+-_count`
- `combo_--+_count`
- `combo_---_count`
- `rebound_combo_++_count`
- `rebound_combo_+-_count`
- `rebound_combo_-+_count`
- `rebound_combo_--_count`

可选增加：

- 各 `zone_combo_3` 对应的平均 `fwd_ret_1d`
- 各 `zone_combo_3` 对应的平均 `fwd_ret_5d`
- 各 `zone_combo_3` 对应的平均 `fwd_ret_20d`
- 各 `rebound_base_combo_2` 对应的平均 `fwd_ret_1d`
- 各 `rebound_base_combo_2` 对应的平均 `fwd_ret_5d`

---

## 11. 有效样本处理规则

### 11.1 最小历史窗口

由于需要 `ma60`，至少要有 60 个交易日历史数据后，才允许输出有效行。

### 11.2 导数缺失处理

以下首日可能为空：

- `d_spread2060`
- `d_dev_low5`
- `day_ret`
- forward return 末尾若超出数据范围也为空

处理原则：

- 缺失值保留为空
- summary 时仅统计有效行

### 11.3 valid_row_flag

建议新增一列：

- `valid_row_flag`

规则：
- 只有当 `ma60`, `spread2060`, `d_spread2060`, `dev_low5`, `d_dev_low5` 均可计算时为 `1`
- 否则为 `0`

---

## 12. 推荐实现路径

### 12.1 建议脚本位置

建议新增：

```text
scripts/export_trend_zone_rebound_features.py
```

首版优先作为独立研究脚本实现，不要一开始写死进正式交易逻辑。

### 12.2 推荐函数拆分

```python
load_or_update_daily_data(ticker, start_date, end_date) -> pd.DataFrame
compute_standard_trend_features(df) -> pd.DataFrame
compute_zone_combo_features(df) -> pd.DataFrame
compute_rebound_base_features(df) -> pd.DataFrame
compute_forward_returns(df, horizons=(1,3,5,10,20)) -> pd.DataFrame
build_single_ticker_feature_table(ticker, start_date, end_date) -> pd.DataFrame
build_multi_ticker_feature_tables(tickers, start_date, end_date) -> tuple[pd.DataFrame, pd.DataFrame]
export_feature_tables(daily_df, summary_df, output_dir) -> None
```

---

## 13. CLI 要求

脚本需支持命令行运行，例如：

```bash
python scripts/export_trend_zone_rebound_features.py \
  --tickers SPY QQQ IWM NVDA \
  --start 2020-01-01 \
  --end 2026-03-31 \
  --output-dir outputs/trend_zone_rebound
```

参数至少包括：

- `--tickers`
- `--start`
- `--end`
- `--output-dir`
- `--auto-update-db`（可选，默认开启）

---

## 14. 验证要求

Codex 完成后，至少验证：

1. 可对 2 个以上 ticker 正常运行。
2. 每个 ticker 能输出完整逐日数据。
3. `zone_combo_3` 能正确输出 8 类正负组合之一。
4. `rebound_base_combo_2` 能正确输出 4 类正负组合之一。
5. `ma60` 不足时不误输出有效组合。
6. CSV 文件能被 Excel 直接打开。
7. summary 中各组合 count 与 daily 文件一致。

---

## 15. 当前阶段最重要的原则

1. 先完整输出研究字段，不提前做语义合并。
2. 先保留全部 8 种 `zone_combo_3` 组合。
3. 先保留全部 4 种 `rebound_base_combo_2` 组合。
4. 所有字段命名清晰、可复算、可追踪。
5. 所有派生字段都必须能从 daily 表重新验证。
6. 优先复用当前项目已有 trend/data 逻辑。
7. 先做研究数据导出，不直接进入正式交易模块。

---

## 16. 对 Codex 的直接任务描述

请基于当前项目已有的数据层与 trend 模块，实现一个多 ticker 研究导出脚本：

- 输入多个 ticker、开始日期、结束日期
- 自动确保本地 daily 数据充足
- 对每个 ticker 计算标准趋势特征
- 新增 `spread2060`, `d_spread2060`, `zone_combo_3`
- 新增 `dev_low5`, `d_dev_low5`, `rebound_base_combo_2`
- 输出逐日明细 CSV
- 输出按 ticker 汇总统计 CSV
- 暂不做区间命名，不做交易信号命名，只输出符号组合


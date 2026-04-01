# Export Trend Decision CSV 任务文档

## 目标
在现有框架中提供一个独立任务脚本：
- 输入 `ticker`、`start_date`、`end_date`、`interval=1d`
- 自动复用现有数据更新流程，确保 `daily.db` 数据覆盖分析范围（含 warmup）
- 输出指定区间内逐日趋势判定结果到 CSV

脚本：`scripts/export_trend_decision_csv.py`

## 复用模块
- `app/data/repository.py`
  - `init_price_db(...)`
  - `load_bars(...)`
- `app/data/updater.py`
  - `update_symbol_data(...)`
- `app/data/providers/yfinance_provider.py`
  - `YFinanceProvider`
- `app/trend/features.py`
  - `compute_ma_features(...)`
- `app/trend/classifier.py`
  - `classify_trend(...)`

## 执行流程
1. 初始化 `daily.db` 的 `daily_bars` 表。
2. 用 `warmup_days`（默认 180 天）向前补齐历史，再更新到 `end_date`。
3. 从 `daily.db` 读取目标 `ticker` 的 `1d` 数据。
4. 基于逐日累计 close 计算 MA / slope 特征。
5. 对每个可计算日调用 `classify_trend(...)`。
6. 仅保留 `[start_date, end_date]` 的结果。
7. 保存到 `outputs/{ticker}_trend_decision_1d.csv`。

## CSV 字段
- `trade_date, ticker, open, high, low, close, volume`
- `ma5, ma20, ma60`
- `slope5, slope20, slope60`
- `ma_order_code, slope_code`
- `trend_type, trend_strength, action_bias`
- `buy_threshold_pct, sell_threshold_pct`
- `rebound_pct, budget_multiplier, reason`

## 异常与日志
- 关键步骤记录 `INFO` 日志（初始化、更新、读取、输出）。
- 更新后从 DB 读取为空时抛出明确异常。
- 特征计算/分类后结果为空时抛出明确异常。

## 使用方式
```bash
python scripts/export_trend_decision_csv.py \
  --ticker SPY \
  --start-date 2025-01-01 \
  --end-date 2025-03-31 \
  --interval 1d \
  --db-path data/raw/daily.db \
  --output-dir outputs \
  --warmup-days 180
```

## 测试
新增测试：`tests/test_export_trend_decision_csv.py`
- 覆盖正常导出路径（生成 CSV + 核心字段校验 + 日期范围校验）
- 覆盖更新后无数据场景（抛出明确异常）

# ML Subsystem Runbook

## 1. 初始化 `buy_strength.db`

```python
from app.ml.buy_strength_label import init_buy_strength_db

init_buy_strength_db()
```

## 2. 更新原始标签

```python
from app.ml.buy_strength_label import update_buy_strength_db

summary = update_buy_strength_db(
    ticker="SPY",
    start_date="2024-01-01",
    end_date="2024-12-31",
)
print(summary)
```

## 3. 获取训练标签 `strength_pct`

```python
from app.ml import get_strength_pct_frame

frame = get_strength_pct_frame(
    tickers=["SPY", "QQQ"],
    end_date="2024-12-31",
    strength_pct_length_month=24,
)
print(frame.head())
```

## 4. 运行一次实验

```python
from app.ml import run_buy_sub_ml_experiment

result = run_buy_sub_ml_experiment(
    tickers=["SPY"],
    end_date="2024-12-31",
    strength_pct_length_month=24,
    model_version="buy/v001",
)
print(result)
```

实验产物会默认写入 `outputs/tmp/buy_sub_ml/...`，包含 `model.pt`、`scaler.pkl`、`feature_columns.json`、`metrics.json` 等文件。

## 5. 升级实验结果为正式模型

```python
from app.ml import promote_buy_model

promote_result = promote_buy_model(
    artifact_dir="outputs/tmp/buy_sub_ml/20260101T000000Z_buy_v001",
    model_version="buy/v001",
)
print(promote_result)
```

正式模型会进入 `models/buy/v001/`，同时更新 `models/buy/registry.json`。

## 6. 运行一次推理输出

```python
from app.ml import infer_buy_strength_pct

csv_path = infer_buy_strength_pct(
    tickers=["SPY"],
    end_date="2024-12-31",
    strength_pct_length_month=24,
    model_version="buy/v001",
)
print(csv_path)
```

推理输出文件名固定为：

```text
{ticker_or_group}_{end_date}_{model_version}_strength_pct_pred.csv
```

其中会至少包含：

- `ticker`
- `date`
- `pred_strength_pct`
- `model_version`

如果同区间真实标签可计算，还会额外带上 `true_strength_pct`。

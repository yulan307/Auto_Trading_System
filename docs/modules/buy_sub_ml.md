# Buy Sub ML

## 概述
`app/ml/buy_sub_ml` 是买入强度回归模型的离线研究模块。
当前实现对应 `docs/research/stage_b_multi_ticker_fullfit_no_ticker_transfer_spec.md`，
目标是在不使用 `ticker` 和时间字段作为模型输入的前提下，学习稳定的 `hist_* -> strength_pct` 映射。

## 数据契约

### 标签来源
- 函数：`app/ml/buy_strength_label/strength_pct.py:get_strength_pct_frame`
- 统一标签列：
  - `ticker`
  - `date`
  - `strength`
  - `strength_pct`

### 特征来源
- 模块：`app/trend/features.py`
- 读取入口：`load_feature_rows(...)`
- 模型输入列：仅数值型 `hist_*`

模型层明确禁止使用：

- `ticker`
- `datetime`
- `fut_*`
- `score`
- `raw_strength`
- `regime`

## 对外入口
- `build_buy_sub_ml_dataset(...)`
  构造训练数据集，输出列为：
  - `ticker`
  - `date`
  - `strength`
  - 排序后的 `hist_*`
  - `strength_pct`
- `fit_strength_model(train_df, ...)`
  低层全样本训练接口，输入应为 `hist_* + strength_pct` 的 DataFrame。
- `predict_strength_pct(hist_df, model_params)`
  低层推理接口，必须严格按 `model_params["feature_columns"]` 的顺序取特征。
- `train_buy_sub_ml_model(...)`
  兼容层包装器，返回实验层需要的模型、指标、预测表和 scaler。
- `run_buy_sub_ml_experiment(...)`
  上层实验入口，负责组装数据集、训练并落盘产物。
- `promote_buy_model(...)`
  将实验产物复制到 `models/buy/<version>/` 并更新 `models/buy/registry.json`。
- `infer_buy_strength_pct(...)`
  读取已发布模型并导出离线推理 CSV。

## 脚本入口
- `scripts/train_buy_sub_ml.py`
  - 输入：`ticker` 可多个、`end_date`
  - 运行时菜单：
    - `1. 学习新模型`
    - `2. 更新已有模型`
  - 新模型会自动生成带时间戳的新版本名
  - 更新已有模型会先列出当前模型，再基于所选模型配置训练，并保存为新的模型目录
- `scripts/infer_buy_sub_ml.py`
  - 输入：`ticker` 可多个、`start_date`、`end_date`
  - 运行时先列出当前模型供选择
  - 按 ticker 逐个运行推理并输出单独 CSV

## 训练规则
- 训练模式：全样本拟合
- 特征选择：按列名字典序排序的数值型 `hist_*`
- 缺失值规则：对 `feature_columns + [strength_pct]` 做严格 `dropna`
- 标准化：`StandardScaler`
- 模型结构：
  - `Linear(input_dim, 64)`
  - `ReLU`
  - `Dropout(0.1)`
  - `Linear(64, 32)`
  - `ReLU`
  - `Dropout(0.1)`
  - `Linear(32, 1)`
  - `Sigmoid`
- 优化器：`Adam`
- 损失函数：加权 MSE
- 样本权重：
  - `weight_i = 1 + alpha * clip(y_i, 0, 1) ** gamma`
  - 默认 `alpha=1.0`
  - 默认 `gamma=2.0`
- 提前停止：
  - 监控 `train_loss`
  - `patience=20`
  - 返回最优训练损失对应的参数

## 返回对象

### `model_params`
至少包含：

- 模型结构参数：
  - `model_type`
  - `input_dim`
  - `hidden_dims`
  - `dropout`
  - `output_activation`
  - `target_column`
- 特征契约：
  - `feature_columns`
  - `feature_count`
  - `feature_order_locked`
- 标准化契约：
  - `scaler_type`
  - `scaler_mean`
  - `scaler_scale`
- 训练超参数：
  - `optimizer`
  - `learning_rate`
  - `weight_decay`
  - `batch_size`
  - `max_epochs`
  - `patience`
  - `loss_function`
  - `target_weight_alpha`
  - `target_weight_gamma`
  - `random_seed`
- 拟合后载荷：
  - `backend`
  - `state_dict` 或 fallback 权重
- 训练摘要：
  - `best_epoch`
  - `best_train_loss`
  - `fit_metrics`

### `train_logs`
至少包含：

- `sample_count`
- `feature_count`
- `train_losses`
- `best_epoch`
- `best_train_loss`
- `fullfit_metrics`

## 产物目录
`run_buy_sub_ml_experiment(...)` 会在 `outputs/tmp/buy_sub_ml/<run_id>_<token>/` 下写出：

- `model.pt`
- `scaler.pkl`
- `feature_columns.json`
- `train_config.json`
- `metrics.json`
- `predictions.csv`
- `notes.md`

其中 `predictions.csv` 保存训练样本明细以及 `pred_strength_pct`。

## 推理 CSV
`infer_buy_strength_pct(...)` 导出的 CSV 包含：

- `ticker`
- `date`
- 训练所需全部 `feature_columns`
- `strength`
- `strength_pct`
- `pred_strength_pct`
- `model_version`

推理流程会从 `feature.db` 读取特征，再通过 `get_strength_pct_frame(...)` 合并标签，并且只对必需特征完整的样本行做预测。

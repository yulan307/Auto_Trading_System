# Stage B 多标的统一模型移植说明

## 1. 目标

本说明用于把当前确认要继续推进的模型版本：

```text
stage_b_multi_ticker_fullfit_no_ticker
```

移植到正式项目中，供项目内 AI 按统一规格实现。

本版本的定位是：

- 使用多个已带标签的标的数据进行**全样本拟合**
- 输入**不包含 ticker，不包含 datetime**
- 输入仅包含 `hist_*` 数值特征
- 标签固定为 `strength_pct`
- 输出模型对 `strength_pct` 的预测值

本版本优先目标不是泛化评估，而是：

> **尽可能贴合当前已有标签数据，得到一个稳定的“hist -> strength_pct”映射函数。**

后续计划是对新的、没有 `strength_pct` 标签的新标的数据，直接调用推理函数，观察预测值是否符合买入时机筛选标准。

---

## 2. 当前确认采用的模型版本

对应实验版本：

```text
outputs/stage_b_multi_ticker_fullfit_no_ticker
```

该版本的核心配置如下：

- 训练模式：全样本拟合，不做 train/valid/test 切分
- 输入特征：146 个 `hist_*` 数值特征
- 不使用 ticker one-hot
- 模型：PyTorch MLP
- 隐层结构：`[64, 32]`
- 激活函数：`ReLU`
- Dropout：`0.1`
- 输出层：`Sigmoid`
- 输出区间：`0 ~ 1`
- 优化器：`Adam`
- 学习率：`1e-3`
- weight decay：`1e-5`
- batch size：`32`
- max epochs：`200`
- patience：`20`
- 损失函数：`MSE`
- 样本加权：启用
- 加权参数：
  - `target_weight_alpha = 1.0`
  - `target_weight_gamma = 2.0`
- 随机种子：`42`
- 输入标准化：`StandardScaler`

当前版本的全样本拟合结果：

- `RMSE = 0.1026`
- `R2 = 0.8437`
- `Pearson = 0.9259`
- `Spearman = 0.7783`

说明：

- 该结果是**全样本拟合口径**
- 不是独立测试集评估口径
- 本版本适合作为“尽量拟合现有标签，再拿去对新样本做投影”的工程版本

---

## 3. 模型参数定义

项目中建议将“模型参数”理解为一个可归档的结构化对象。

本说明只定义其内容，不负责归档方式。

建议命名：

```python
model_params
```

建议至少包含以下字段：

### 3.1 模型结构参数

- `model_type`: 固定为 `"mlp_regressor"`
- `input_dim`: 输入维度，当前版本为 `146`
- `hidden_dims`: 当前版本为 `[64, 32]`
- `dropout`: 当前版本为 `0.1`
- `output_activation`: 固定为 `"sigmoid"`
- `target_column`: 固定为 `"strength_pct"`

### 3.2 特征参数

- `feature_columns`: 训练时实际使用的特征列名列表
- `feature_count`: 当前版本为 `146`
- `feature_order_locked`: 固定为 `True`

说明：

- 推理时必须严格按 `feature_columns` 的顺序组装输入矩阵
- 不允许依赖 DataFrame 当前列顺序

### 3.3 标准化参数

- `scaler_type`: 固定为 `"StandardScaler"`
- `scaler_mean`: 每个特征的均值数组
- `scaler_scale`: 每个特征的标准差数组

### 3.4 训练参数

- `optimizer`: 固定为 `"Adam"`
- `learning_rate`: `1e-3`
- `weight_decay`: `1e-5`
- `batch_size`: `32`
- `max_epochs`: `200`
- `patience`: `20`
- `loss_function`: `"mse"`
- `target_weight_alpha`: `1.0`
- `target_weight_gamma`: `2.0`
- `random_seed`: `42`

### 3.5 模型权重

- `state_dict` 或项目内等价的神经网络参数对象

### 3.6 训练结果摘要

建议附带：

- `best_epoch`
- `best_train_loss`
- `fit_metrics`

其中 `fit_metrics` 建议至少包含：

- `fullfit_mae`
- `fullfit_rmse`
- `fullfit_r2`
- `fullfit_pearson`
- `fullfit_spearman`
- `top5_overlap_count`
- `top10_overlap_count`
- `top20_overlap_count`

---

## 4. 学习函数

### 4.1 函数职责

学习函数用于：

- 接收一份已经准备好的训练 DataFrame
- 从中识别 `hist_*` 特征与标签
- 在全样本上训练模型
- 返回模型参数与训练日志

本函数**不负责**：

- 模型参数归档
- 文件写入
- 外部数据库读写
- 业务工作流调度

### 4.2 输入

输入为一个 DataFrame，命名建议：

```python
train_df
```

要求：

- 不含 `ticker`
- 不含 `datetime`
- 只包含：
  - `hist_*` 数值列
  - 标签列 `strength_pct`

即：

```text
输入列 = hist_* + strength_pct
```

约束：

- `strength_pct` 必须存在
- 至少存在 1 个 `hist_*` 数值列
- 所有参与训练的列必须为数值型
- 不允许在本函数内做未来特征拼接
- 不允许在本函数内自动补 ticker 编码

### 4.3 缺失值规则

本函数必须使用严格口径：

```python
df_model = train_df[feature_columns + [target_column]].dropna().copy()
```

即：

- 不填充缺失值
- 不插值
- 不前向填充
- 仅保留输入与标签都完整的样本

### 4.4 特征选择规则

本函数必须自动选择：

```python
feature_columns = sorted(
    c for c in train_df.columns
    if c.startswith("hist_")
    and c != "strength_pct"
)
```

说明：

- 项目内实现时，建议固定为**按列名字典序排序**
- 这样训练与推理的特征顺序天然可复现

### 4.5 标准化规则

必须使用：

```text
StandardScaler
```

规则：

- 在清洗后的全样本上 `fit`
- 再将同一份样本 `transform`
- 保存 `mean` 和 `scale` 到 `model_params`

说明：

- 这是全样本拟合版本
- 所以 scaler 不存在 train/test 边界问题

### 4.6 模型定义

模型结构固定建议如下：

```text
Input(146)
-> Linear(146, 64)
-> ReLU
-> Dropout(0.1)
-> Linear(64, 32)
-> ReLU
-> Dropout(0.1)
-> Linear(32, 1)
-> Sigmoid
```

输出：

```text
pred_strength_pct ∈ [0, 1]
```

### 4.7 损失函数定义

当前版本使用加权 MSE。

先定义逐样本误差：

```text
base_loss_i = (pred_i - y_i)^2
```

再定义样本权重：

```text
weight_i = 1 + alpha * (clip(y_i, 0, 1) ** gamma)
```

当前版本：

- `alpha = 1.0`
- `gamma = 2.0`

最终 loss：

```text
loss = sum(base_loss_i * weight_i) / sum(weight_i)
```

含义：

- 对高 `strength_pct` 样本赋予更高权重
- 让模型更关注高强度区域的拟合

### 4.8 训练停止规则

本版本是全样本拟合，不存在验证集。

因此建议：

- 每轮记录一次 `train_loss`
- 维护“当前最优训练损失”
- 若连续 `patience=20` 轮没有更优，则提前停止
- 返回训练损失最优时的模型参数

### 4.9 输出

本函数返回两个对象：

```python
model_params, train_logs = fit_strength_model(train_df)
```

#### `model_params`

必须包含：

- 模型结构参数
- 特征列顺序
- scaler 参数
- 网络权重
- 训练超参数

#### `train_logs`

建议至少包含：

- `sample_count`
- `feature_count`
- `train_losses`
- `best_epoch`
- `best_train_loss`
- `fullfit_metrics`

### 4.10 建议函数签名

```python
def fit_strength_model(
    train_df: pd.DataFrame,
    *,
    target_column: str = "strength_pct",
    hidden_dims: tuple[int, ...] = (64, 32),
    dropout: float = 0.1,
    learning_rate: float = 1e-3,
    weight_decay: float = 1e-5,
    batch_size: int = 32,
    max_epochs: int = 200,
    patience: int = 20,
    loss_function: str = "mse",
    target_weight_alpha: float = 1.0,
    target_weight_gamma: float = 2.0,
    random_seed: int = 42,
) -> tuple[dict, dict]:
    ...
```

---

## 5. 推理函数

### 5.1 函数职责

推理函数用于：

- 接收已准备好的 hist 特征数据
- 接收模型参数
- 输出预测的 `strength_pct`

本函数**不负责**：

- 读取模型参数
- 读取数据库
- 构造 hist 特征
- ticker / datetime 处理

这些都应由前置函数完成。

### 5.2 输入

输入包括两个对象：

```python
hist_df
model_params
```

其中：

#### `hist_df`

要求：

- 不含 `ticker`
- 不含 `datetime`
- 只包含或至少包含 `hist_*` 特征列

#### `model_params`

必须包含：

- `feature_columns`
- `scaler_mean`
- `scaler_scale`
- 模型结构参数
- 模型权重

### 5.3 推理前校验

推理函数必须先校验：

1. `model_params["feature_columns"]` 中的全部列在 `hist_df` 中存在
2. 所需列均为数值列
3. 所需列中不允许出现缺失值

推荐策略：

- 若缺列，直接抛错
- 若存在缺失值，直接抛错

本函数不负责做缺失修复

### 5.4 推理流程

流程固定为：

1. 按 `feature_columns` 的顺序取列
2. 转为数值矩阵 `X`
3. 使用 `scaler_mean` 和 `scaler_scale` 做标准化
4. 加载模型结构和权重
5. 前向推理
6. 输出预测值

由于输出层是 `Sigmoid`：

```text
pred_strength_pct ∈ [0, 1]
```

### 5.5 输出

建议输出为一维数组或 Series：

```python
pred_strength_pct
```

若调用端需要 DataFrame，可由上层自行封装。

### 5.6 建议函数签名

```python
def predict_strength_pct(
    hist_df: pd.DataFrame,
    model_params: dict,
) -> np.ndarray:
    ...
```

---

## 6. 实现约束

### 6.1 学习与推理都必须遵守

- 不使用 ticker
- 不使用 datetime
- 不使用 `fut_*`
- 不使用 `score`
- 不使用 `raw_strength`
- 不使用 `regime`

### 6.2 输出值约束

输出值必须满足：

```text
0 <= pred_strength_pct <= 1
```

### 6.3 特征顺序约束

推理时严禁：

- 依赖 DataFrame 原始列顺序
- 依赖调用方随意传入的列顺序

必须：

- 完全按训练时保存的 `feature_columns` 顺序构造输入

### 6.4 项目内推荐做法

建议将实现分为三层：

1. `fit_strength_model(train_df) -> model_params, train_logs`
2. `predict_strength_pct(hist_df, model_params) -> y_pred`
3. 上层业务接口负责模型参数归档、版本管理、调用前数据准备

---

## 7. 对新 ticker 的使用建议

虽然当前推进版本是：

```text
stage_b_multi_ticker_fullfit_no_ticker
```

它依然是基于已有 6 个 ticker 的标签分布训练出来的。

因此对未来“新 ticker，无标签”的使用建议是：

- 先保证 hist 特征口径与训练数据完全一致
- 先将新 ticker 的 hist 数据按训练特征顺序组装
- 再调用推理函数得到 `pred_strength_pct`
- 重点关注高分样本是否符合业务上的买入时机判断

建议后续业务筛选重点观察：

- 预测值是否集中在某些结构性位置
- 高预测值是否对应你定义中的“下跌后开始反转”区域
- 新 ticker 的预测分布是否与已知 ticker 差异过大

---

## 8. 一句话定义

本移植版本是一个**不使用 ticker、不使用时间字段、仅依赖 `hist_*` 特征并输出 `strength_pct` 的全样本拟合 MLP 回归模型**；项目内需要实现两个核心函数：

- 学习函数：输入 `hist_* + strength_pct` 的 DataFrame，输出 `model_params + train_logs`
- 推理函数：输入 `hist_*` 数据和 `model_params`，输出预测的 `strength_pct`


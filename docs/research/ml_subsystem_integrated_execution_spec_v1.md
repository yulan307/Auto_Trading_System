# ML 子系统接入方案（执行规格版）

## 0. 文档定位

本文件不是讨论稿，而是面向实现代理 / Codex 的**执行规格版**。

目标是在当前 `Auto_Trading_System` 仓库中，按既定模块边界实现一条完整的买入子模型链路：

```text
feature.db
→ buy_strength_label（原始 strength 生成与维护）
→ buy_strength.db
→ get_strength_pct_frame(...)
→ buy_sub_ml（训练 / 评估 / 推理）
→ outputs/tmp/buy_sub_ml/
→ models/buy/v001
→ runtime 读取 buy_model_version
```

---

## 1. 本轮必须完成的目标

Codex 本轮必须完成以下事项：

1. 在 `app/ml/` 下建立正式模块骨架
2. 建立 `data/buy_strength.db`
3. 实现原始 `strength` 标签的初始化与增量更新
4. 实现统一标签入口函数 `get_strength_pct_frame(...)`
5. 实现 `buy_sub_ml` 的稳定层：
   - dataset
   - feature_selector
   - trainer
   - artifact
   - inference
   - registry
6. 实现第一版训练入口
7. 实现第一版推理入口
8. 在 `app/runtime` 中加入 ML 版本号配置读取
9. 生成必要的测试与最小运行说明

---

## 2. 本轮不做的事情

本轮不要做：

- 不要实现 sell 模型训练
- 不要把 ML 结果直接接入 live 交易决策
- 不要在 `app/trend/` 中混入训练逻辑
- 不要设计复杂统一插件系统
- 不要做 UI / Streamlit
- 不要做自动超参数搜索
- 不要把每次实验结果直接注册为正式模型版本

---

## 3. 目录结构要求

必须新增或补齐以下目录与文件：

```text
app/
├─ ml/
│  ├─ __init__.py
│  ├─ common/
│  │  ├─ __init__.py
│  │  ├─ paths.py
│  │  ├─ schemas.py
│  │  └─ utils.py
│  ├─ buy_strength_label/
│  │  ├─ __init__.py
│  │  ├─ db.py
│  │  ├─ init_db.py
│  │  ├─ repository.py
│  │  ├─ generator.py
│  │  ├─ updater.py
│  │  └─ strength_pct.py
│  └─ buy_sub_ml/
│     ├─ __init__.py
│     ├─ dataset.py
│     ├─ feature_selector.py
│     ├─ trainer.py
│     ├─ experiment.py
│     ├─ inference.py
│     ├─ artifact.py
│     └─ registry.py

models/
├─ buy/
│  ├─ registry.json
│  └─ .gitkeep
└─ sell/
   └─ .gitkeep

tests/
├─ test_buy_strength_db.py
├─ test_strength_pct.py
├─ test_buy_sub_ml_dataset.py
└─ test_buy_sub_ml_inference.py
```

允许根据仓库实际情况新增少量辅助文件，但不得破坏上述主结构。

---

## 4. runtime 接入要求

### 4.1 配置文件要求

在配置中增加：

```yaml
ml:
  enabled: true
  buy_model_version: buy/v001
  sell_model_version: null
```

### 4.2 runtime context 要求

在 runtime context 中加入：

```python
runtime_context["ml"] = {
    "enabled": True,
    "buy_model_version": "buy/v001",
    "sell_model_version": None,
}
```

### 4.3 当前阶段用途

当前阶段 runtime 只负责：
- 读取 ML 开关
- 读取 `buy_model_version`
- 为后续 backtest / paper / live 的推理接入预留统一入口

当前阶段不要求：
- 直接控制买卖决策
- 自动联动 execution

---

## 5. 数据库与数据契约

## 5.1 `feature.db`

视为已存在，由 `app/trend/feature.py` 维护。  
ML 子系统不得重写 feature 生成逻辑，只允许复用：

- `update_feature_db(...)`
- `load_feature_rows(...)`

## 5.2 `buy_strength.db`

数据库文件：

```text
data/buy_strength.db
```

表名固定为：

```text
buy_strength_daily
```

字段要求：

- `ticker TEXT NOT NULL`
- `date TEXT NOT NULL`
- `strength REAL NOT NULL`
- `label_version TEXT NULL`
- `update_time TEXT NOT NULL`

主键：

```text
(ticker, date)
```

索引：
- 唯一索引 `(ticker, date)`
- 普通索引 `(ticker)`

说明：
- 本库保存的是原始 `strength`
- 不保存最终学习目标 `strength_pct`

---

## 6. 标签算法固定规则

本轮实现必须直接按当前标签策略实现原始标签生成。

### 6.1 基础分数

```text
score = max(-fut_low_dev_w, -fut_low_dev_m, 0)
```

### 6.2 原始强度

```text
raw_strength = max(score * fut_low_dev_drv2_w, 0)
```

### 6.3 原始库存储规则

写入 `buy_strength.db` 的 `strength` 字段时，当前版本直接保存：

```text
strength = raw_strength
```

### 6.4 label_version

当前实现建议固定写为：

```text
reversal_strength_v1
```

后续如标签算法升级，再变更版本号。

---

## 7. `buy_strength_label` 模块执行规格

## 7.1 `init_db.py`

必须提供：

```python
def init_buy_strength_db(db_path: str = "data/buy_strength.db") -> None:
    ...
```

职责：
- 创建数据库
- 创建 `buy_strength_daily`
- 建立主键与索引

---

## 7.2 `repository.py`

至少实现以下函数：

```python
def upsert_strength_rows(
    df,
    db_path: str = "data/buy_strength.db",
    table_name: str = "buy_strength_daily",
) -> int:
    ...

def load_strength_rows(
    tickers,
    start_date: str,
    end_date: str,
    db_path: str = "data/buy_strength.db",
    table_name: str = "buy_strength_daily",
):
    ...

def get_existing_strength_dates(
    ticker: str,
    start_date: str,
    end_date: str,
    db_path: str = "data/buy_strength.db",
    table_name: str = "buy_strength_daily",
) -> set[str]:
    ...
```

要求：
- 支持单 ticker 和多 ticker
- 返回标准 DataFrame
- 日期字段统一为 `date`
- 不允许 silent failure

---

## 7.3 `generator.py`

至少实现：

```python
def compute_raw_strength_from_feature_df(feature_df):
    ...
```

输入：
- 来自 `feature.db` 的特征 DataFrame

要求：
- 必须校验所需列存在：
  - `fut_low_dev_w`
  - `fut_low_dev_m`
  - `fut_low_dev_drv2_w`
- 输出至少包含：
  - `ticker`
  - `date`
  - `strength`
  - `label_version`
  - `update_time`

计算规则：
- `score = max(-fut_low_dev_w, -fut_low_dev_m, 0)`
- `strength = max(score * fut_low_dev_drv2_w, 0)`

---

## 7.4 `updater.py`

必须提供：

```python
def update_buy_strength_db(
    ticker: str,
    start_date: str,
    end_date: str,
    feature_db_path: str = "data/feature.db",
    strength_db_path: str = "data/buy_strength.db",
) -> dict:
    ...
```

执行流程必须为：

1. 检查 `buy_strength.db` 已有 `(ticker, date)` 记录
2. 已有数据默认完整有效，直接跳过
3. 识别新增缺失区间
4. 通过 `app/trend/feature.py`：
   - 调用 `update_feature_db(...)`
   - 调用 `load_feature_rows(...)`
5. 读取新增区间对应的 feature 行
6. 调用 `compute_raw_strength_from_feature_df(...)`
7. 写入 `buy_strength.db`

若未来窗口不足导致某些日期无法计算，则：
- 不写入这些日期
- 不报错终止
- 记录跳过数量

输出至少包含：

```python
{
    "ticker": "SPY",
    "start_date": "2024-01-01",
    "end_date": "2026-03-31",
    "existing_rows": 0,
    "new_rows": 0,
    "skipped_rows": 0,
    "status": "ok"
}
```

---

## 8. `strength_pct` 统一入口函数执行规格

这是本轮最核心接口。

### 8.1 文件位置

```text
app/ml/buy_strength_label/strength_pct.py
```

### 8.2 必须提供的函数

```python
def get_strength_pct_frame(
    tickers,
    end_date: str | None = None,
    strength_pct_length_month: int = 24,
    feature_db_path: str = "data/feature.db",
    strength_db_path: str = "data/buy_strength.db",
) -> "pd.DataFrame":
    ...
```

### 8.3 函数职责

该函数必须作为：

- 训练标签入口
- 推理分析真实标签入口
- 后续研究分析统一入口

### 8.4 输入规则

- `tickers`
  - 支持 `str` 或 `list[str]`
- `end_date`
  - 为空则默认今天
- `strength_pct_length_month`
  - 按**自然月**理解
- 百分位历史窗口
  - 固定为**自然日回推 2 年**

### 8.5 计算规则

#### 8.5.1 读取范围
底层读取起点必须为：

```text
read_start_date = end_date - strength_pct_length_month - 2年
```

#### 8.5.2 多 ticker 处理
当前版本按：
- **ticker 各自独立**计算 `strength_pct`

多个 ticker 输入时：
- 逐 ticker 独立计算
- 最后 concat

#### 8.5.3 原始强度补齐
函数内部必须检查 `buy_strength.db` 是否已有足够原始 `strength` 数据。若不足，应自动调用：

```python
update_buy_strength_db(...)
```

#### 8.5.4 百分位定义
当前版本使用：

- 对每个 ticker 的 `strength`
- 在当前历史窗口内
- 计算其相对百分位位置
- 输出 `strength_pct`

当前阶段默认采用简单分位实现即可，但代码结构要允许以后替换成更严格的策略版本。

### 8.6 返回列要求

默认返回至少包含：

- `ticker`
- `date`
- `strength`
- `label_version`
- `strength_pct`

### 8.7 输出区间要求

返回结果最终只保留：

```text
[end_date - strength_pct_length_month, end_date]
```

---

## 9. `buy_sub_ml` 模块执行规格

## 9.1 总体原则

`buy_sub_ml` 只负责：
- 使用 `hist_*` 特征
- 学习 `strength_pct`
- 输出实验模型与分析结果

不得：
- 自己重复实现 `strength_pct` 逻辑
- 直接改写 `buy_strength.db`
- 依赖 `fut_*` 作为输入特征

---

## 9.2 `feature_selector.py`

必须提供：

```python
def select_hist_feature_columns(df) -> list[str]:
    ...
```

规则：
- 只允许选择以 `hist_` 开头的数值列
- 严禁引入：
  - `fut_*`
  - `strength`
  - `strength_pct`
  - `score`
  - `raw_strength`
  - 其他标签泄漏字段

---

## 9.3 `dataset.py`

必须提供：

```python
def build_buy_sub_ml_dataset(
    tickers,
    end_date: str | None,
    strength_pct_length_month: int,
    feature_db_path: str = "data/feature.db",
    strength_db_path: str = "data/buy_strength.db",
):
    ...
```

执行流程必须为：

1. 调用 `get_strength_pct_frame(...)`
2. 读取 feature.db 对应区间数据
3. 仅提取 `hist_*` 输入列
4. 按 `ticker,date` join
5. 删除输入缺失或标签缺失样本
6. 返回标准训练 DataFrame

返回结果至少包含：
- `ticker`
- `date`
- 输入特征列
- `strength_pct`

---

## 9.4 `trainer.py`

必须提供一个最小可运行的 PyTorch 训练器。

至少实现：

```python
def train_buy_sub_ml_model(
    df,
    feature_columns: list[str],
    target_column: str = "strength_pct",
    config: dict | None = None,
) -> dict:
    ...
```

当前默认要求：

- 框架：PyTorch
- 目标：回归 `strength_pct`
- 自动检测 GPU / CPU
- 标准化输入
- 输出：
  - 模型对象 / 权重
  - scaler
  - metrics
  - predictions

当前模型允许先用一个最小 MLP，例如：

```text
Linear(input_dim, 128)
ReLU
Dropout(0.1)
Linear(128, 64)
ReLU
Dropout(0.1)
Linear(64, 1)
```

### 训练切分方式
本轮先不要钉死在主文档里。  
实现上建议：
- 支持通过 config 选择切分方式
- 默认先用随机切分
- 保留以后切时间切分的扩展口

---

## 9.5 `artifact.py`

必须实现模型产物保存。

至少提供：

```python
def save_experiment_artifacts(
    artifact_dir: str,
    model,
    scaler,
    feature_columns: list[str],
    train_config: dict,
    metrics: dict,
    predictions_df,
) -> None:
    ...
```

必须保存：
- `model.pt`
- `scaler.pkl`
- `feature_columns.json`
- `train_config.json`
- `metrics.json`
- `predictions.csv`

若便于实现，也建议额外保存：
- `notes.md`

---

## 9.6 `experiment.py`

必须提供实验入口：

```python
def run_buy_sub_ml_experiment(
    tickers,
    end_date: str | None,
    strength_pct_length_month: int,
    model_version: str | None = None,
    feature_db_path: str = "data/feature.db",
    strength_db_path: str = "data/buy_strength.db",
    output_dir: str = "outputs/tmp/buy_sub_ml",
    config: dict | None = None,
) -> dict:
    ...
```

执行流程必须为：

1. 调用 `build_buy_sub_ml_dataset(...)`
2. 调用 `select_hist_feature_columns(...)`
3. 调用 `train_buy_sub_ml_model(...)`
4. 生成实验目录
5. 调用 `save_experiment_artifacts(...)`
6. 返回实验摘要

返回至少包含：

```python
{
    "tickers": ["SPY"],
    "train_rows": 0,
    "valid_rows": 0,
    "test_rows": 0,
    "feature_count": 0,
    "artifact_dir": "outputs/tmp/buy_sub_ml/...",
    "status": "ok"
}
```

---

## 9.7 `registry.py`

必须提供正式模型升级入口：

```python
def promote_buy_model(
    artifact_dir: str,
    model_version: str,
    model_root: str = "models/buy",
    registry_path: str = "models/buy/registry.json",
) -> dict:
    ...
```

职责：
- 将实验产物复制到 `models/buy/{model_version}/`
- 更新 `models/buy/registry.json`

注意：
- 实验结果默认不自动注册
- 必须手动调用 promote 才进入正式模型区

---

## 9.8 `inference.py`

必须提供：

```python
def infer_buy_strength_pct(
    tickers,
    end_date: str | None,
    strength_pct_length_month: int,
    model_version: str,
    feature_db_path: str = "data/feature.db",
    strength_db_path: str = "data/buy_strength.db",
    model_root: str = "models/buy",
    output_dir: str = "outputs/tmp/buy_sub_ml",
) -> str:
    ...
```

执行流程必须为：

1. 加载指定模型版本：
   - model
   - scaler
   - feature_columns
2. 通过 `update_feature_db(...)` / `load_feature_rows(...)` 读取最新特征
3. 提取一致的 `hist_*` 输入列
4. 生成 `pred_strength_pct`
5. 如可行，则通过 `get_strength_pct_frame(...)` 生成同区间 `true_strength_pct`
6. 输出分析用 CSV

### 输出文件命名固定为

```text
{ticker_or_group}_{end_date}_{model_version}_strength_pct_pred.csv
```

输出内容至少包含：
- `ticker`
- `date`
- `pred_strength_pct`
- `model_version`

若能对照真实值，则增加：
- `true_strength_pct`

---

## 10. `models/buy` 目录执行要求

## 10.1 `registry.json`

若不存在则自动初始化为：

```json
{
  "active_version": null,
  "versions": {}
}
```

## 10.2 正式版本目录

每个正式版本目录至少包含：

```text
models/buy/v001/
├─ model.pt
├─ scaler.pkl
├─ feature_columns.json
├─ train_config.json
├─ metrics.json
└─ notes.md
```

---

## 11. 测试要求

本轮至少补齐以下测试。

### 11.1 `test_buy_strength_db.py`
验证：
- `init_buy_strength_db` 可创建数据库
- `update_buy_strength_db` 可写入数据
- 重复调用时已存在数据会跳过

### 11.2 `test_strength_pct.py`
验证：
- `get_strength_pct_frame(...)` 可返回 DataFrame
- 返回列包含：
  - `ticker`
  - `date`
  - `strength`
  - `label_version`
  - `strength_pct`
- 多 ticker 时可正常 concat

### 11.3 `test_buy_sub_ml_dataset.py`
验证：
- `build_buy_sub_ml_dataset(...)` 可拼装训练数据
- 输入列只包含 `hist_*`
- 标签列为 `strength_pct`

### 11.4 `test_buy_sub_ml_inference.py`
验证：
- 可从假模型 / 最小模型加载
- 可输出分析 CSV
- 文件命名符合规范

---

## 12. 最小运行说明要求

必须补充一份最小运行说明，文件名建议：

```text
docs/research/ml_subsystem_runbook.md
```

内容至少说明：

1. 如何初始化 `buy_strength.db`
2. 如何更新原始标签
3. 如何调用 `get_strength_pct_frame(...)`
4. 如何运行一次实验
5. 如何把实验结果升级为正式模型
6. 如何运行一次推理输出

---

## 13. 推荐开发顺序（强制）

必须按以下顺序推进：

### 第 1 步
建立目录与空文件骨架

### 第 2 步
实现 `buy_strength.db`
- init
- repository
- generator
- updater

### 第 3 步
实现 `get_strength_pct_frame(...)`

### 第 4 步
实现 `buy_sub_ml` 的稳定层
- feature_selector
- dataset
- artifact
- inference

### 第 5 步
实现训练器与实验入口
- trainer
- experiment

### 第 6 步
实现模型注册升级
- registry
- promote

### 第 7 步
接入 runtime 配置读取

### 第 8 步
补测试与运行说明

---

## 14. 验收标准

本轮完成后，必须满足：

1. `buy_strength.db` 可初始化
2. `buy_strength.db` 可按增量方式补齐原始 `strength`
3. `get_strength_pct_frame(...)` 可返回可训练标签数据
4. `buy_sub_ml` 可基于 `hist_*` 训练一个最小模型
5. 训练结果可落到 `outputs/tmp/buy_sub_ml/...`
6. 模型可手动升级到 `models/buy/v001`
7. `runtime` 可读取 `buy_model_version`
8. 推理函数可输出：
   - `{ticker_or_group}_{end_date}_{model_version}_strength_pct_pred.csv`
9. 至少有 4 个对应测试文件
10. 所有函数有 type hints，关键步骤有日志

---

## 15. 给 Codex 的最终指令

请直接按本文档实现，不要擅自改变以下核心约束：

- `buy_strength.db` 保存的是原始 `strength`
- 真正学习目标是动态计算的 `strength_pct`
- `strength_pct` 统一通过 `get_strength_pct_frame(...)` 获取
- 输入特征只允许使用 `hist_*`
- 正式模型只放在 `models/buy/`
- 实验产物默认只放在 `outputs/tmp/buy_sub_ml/`
- 当前阶段 runtime 只记录模型版本，不直接控制交易决策

优先保证：
- 结构清晰
- 接口稳定
- 可运行
- 可复查
- 便于后续继续迭代

# PC Abaqus 接力清单

Mac 端没有 Abaqus。本批次已准备 3 个训练样本和 1 个验证样本，PC 端只负责运行真实 Abaqus 导出、转换、登记和验证，不得用 C++ 输出代替参考矩阵。

## 1. 拉取项目并检查数据计划

在 PC 的 Git 工作目录拉取最新分支，然后运行：

```bat
python -m stiffness_agent validate-data-plan data\datasets\plans\s4_distorted_train_batch.json
python -m stiffness_agent validate-data-plan data\datasets\plans\s4_skew_validation_batch.json
```

## 2. 在 Abaqus Command 中运行四个作业

```bat
abaqus job=s4_train_001_trapezoid_far input=data\reference\abaqus\input_decks\s4_train_001_trapezoid_far_matrix_export.inp interactive
abaqus job=s4_train_002_long_rectangle input=data\reference\abaqus\input_decks\s4_train_002_long_rectangle_matrix_export.inp interactive
abaqus job=s4_train_003_node_down input=data\reference\abaqus\input_decks\s4_train_003_node_down_matrix_export.inp interactive
abaqus job=s4_validation_001_skew input=data\reference\abaqus\input_decks\s4_validation_001_skew_matrix_export.inp interactive
```

若只生成 `_X1.sim`，逐个执行：

```bat
abaqus mtxasm job=s4_train_001_trapezoid_far_X1 text
abaqus mtxasm job=s4_train_002_long_rectangle_X1 text
abaqus mtxasm job=s4_train_003_node_down_X1 text
abaqus mtxasm job=s4_validation_001_skew_X1 text
```

## 3. 转换矩阵

对每个实际生成的 `*_STIF-1.mtx` 运行转换脚本。例如：

```bat
python scripts\abaqus\convert_abaqus_mtx_to_csv.py s4_train_001_trapezoid_far_X1_STIF-1.mtx data\reference\abaqus\matrices\s4_train_001_trapezoid_far_reference.csv
```

其余三个样本使用相同命名规则。转换脚本必须报告 `24 x 24`，并通过有限值、对称性和矩阵尺寸校验。

## 4. 创建元数据并登记划分

参考 `data/reference/abaqus/metadata/sample_001.json` 为四个样本创建元数据，必须记录真实 `.mtx` 文件名、导出方法和解析条目数。随后登记：

```bat
python -m stiffness_agent register-sample --meta data\reference\abaqus\metadata\s4_train_001_trapezoid_far.json --split train
python -m stiffness_agent register-sample --meta data\reference\abaqus\metadata\s4_train_002_long_rectangle.json --split train
python -m stiffness_agent register-sample --meta data\reference\abaqus\metadata\s4_train_003_node_down.json --split train
python -m stiffness_agent register-sample --meta data\reference\abaqus\metadata\s4_validation_001_skew.json --split validation
python -m stiffness_agent verify-dataset
```

## 5. 给 PC Codex 的接力目标

1. 确认四个 Abaqus job 无错误完成，保留必要日志作为来源证据。
2. 生成四个真实 CSV 和对应元数据，不修改四个样本的节点、材料或厚度。
3. 将三个训练样本登记为 `train`，斜平行四边形登记为 `validation`。
4. 运行 Python 测试、C++ 测试和 `verify-dataset`，记录每个样本的 Frobenius 相对误差。
5. 提交并推送 Abaqus 产物、元数据、数据集清单和验证报告。

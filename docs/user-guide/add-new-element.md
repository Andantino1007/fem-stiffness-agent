# 接入新单元与新增样本

本页区分两种任务：给当前单元增加样本，以及接入一套新的单元实现。

## 只增加一个样本

以当前 S4 项目为例，一个新样本需要：

1. 新的 Abaqus 输入文件；
2. 真实导出的原始矩阵和证据日志；
3. 转换后的参考矩阵 CSV；
4. 样本元数据 JSON；
5. 数据集登记；
6. 重新生成的实现矩阵和验证报告。

推荐顺序：

```text
设计几何与材料
-> 运行可信求解器
-> 导出原始矩阵
-> 转换并校验 CSV
-> 填写元数据
-> register-sample
-> verify
-> verify-dataset --development
```

登记前先确认参考矩阵不是由待验证实现生成的，也没有覆盖已有样本。

```bash
python -m shell_agent register-sample \
  --meta data/abaqus/meta/<sample_id>.json \
  --split train
```

`--split` 可选 `train`、`validation`、`test`。登记 `test` 会重建测试集哈希锁。

## 接入新单元前的清单

先明确以下契约：

- 单元名称和节点数；
- 每节点自由度及全矩阵自由度顺序；
- 刚度矩阵尺寸；
- 几何、材料、截面和积分参数；
- 可信参考矩阵的生成方法；
- 实现程序如何读取一个样本；
- 实现程序把矩阵写到哪里；
- 编译命令和测试命令。

## 推荐目录

新单元推荐按单元归档实现和数据，避免与 S4 文件混在一起：

```text
elements/beam2/
├── include/                 梁单元公开接口
├── src/                     梁单元实现和 CLI
└── tests/                   梁单元测试

data/beam2/
├── meta/                    样本元数据
├── raw/                     求解器原始导出
├── evidence/                作业日志
├── reference/               可信参考矩阵 CSV
└── actual/                  实现矩阵 CSV
```

这是推荐布局，不是框架硬编码要求。现有 S4 保留历史目录 `include/shell/`、`src/shell/`、`tests/` 和 `data/abaqus/`。

## 完整示例：接入一个 6 x 6 梁单元

假设是二维两节点梁，每节点自由度为 `ux、uy、rz`，总矩阵为 `6 x 6`。

### 1. 配置项目

把 `workflow/project.example.json` 复制为项目配置并修改为：

```json
{
  "schema_version": 1,
  "project_id": "beam2-stiffness",
  "element_type": "BEAM2",
  "matrix_dimensions": [6, 6],
  "node_count": 2,
  "dof_labels_per_node": ["ux", "uy", "rz"],
  "diagnostic_groups": {
    "axial": ["ux"],
    "bending": ["uy", "rz"]
  },
  "dataset": "data/datasets/beam2.json",
  "primary_sample": "data/beam2/meta/train_001.json",
  "reference_generation_methods": ["matrix_generate"],
  "adapter": {
    "kind": "command",
    "build_command": ["cmake", "--build", "build/beam2"],
    "evaluate_command": ["build/beam2/beam2_cli", "{sample}"],
    "test_command": ["ctest", "--test-dir", "build/beam2", "--output-on-failure"]
  },
  "agent": {
    "allowed_patch_paths": ["elements/beam2/src/Beam2.cpp"],
    "test_paths": ["elements/beam2/tests/beam2_tests.cpp"],
    "experiment_classes": ["formulation", "integration", "dof_mapping"]
  },
  "acceptance": {
    "target_error": 0.01
  }
}
```

### 2. 创建样本元数据

`data/beam2/meta/train_001.json`：

```json
{
  "sample_id": "beam2_train_001",
  "element_type": "BEAM2",
  "parameters": {
    "nodes": [[0.0, 0.0], [1.0, 0.0]],
    "E": 210000000000.0,
    "area": 0.01,
    "inertia": 8.333333333e-6,
    "dof_order_per_node": ["ux", "uy", "rz"]
  },
  "reference_matrix_source": {
    "status": "real_abaqus_export",
    "solver": "Abaqus 2024",
    "job": "beam2_train_001",
    "method": "MATRIX GENERATE"
  },
  "reference_matrix": "data/beam2/reference/train_001.csv",
  "implementation_matrix": "data/beam2/actual/train_001.csv"
}
```

`parameters` 由适配器解释，公共层不限定梁单元字段；但自由度顺序、单位和来源必须写清楚。

### 3. 准备两个矩阵文件

- `reference_matrix`：可信求解器生成，不能由待验证实现代替；
- `implementation_matrix`：由 `evaluate_command` 每次重新生成。

两者都必须是无表头 `6 x 6` CSV。

### 4. 实现 command 适配器

适配器命令按参数数组直接执行，不经过 shell。可使用的占位符：

| 占位符 | 内容 |
| --- | --- |
| `{root}` | 仓库根目录绝对路径 |
| `{project}` | 项目配置路径 |
| `{sample}` | 当前样本元数据路径 |
| `{report}` | 当前验证报告路径 |

`evaluate_command` 的最低责任是读取 `{sample}`，计算矩阵，并写到元数据的 `implementation_matrix`。公共层随后读取两个 CSV 并生成统一报告。

### 5. 创建数据集

`data/datasets/beam2.json`：

```json
{
  "schema_version": 2,
  "project_id": "beam2-stiffness",
  "train": ["data/beam2/meta/train_001.json"],
  "validation": [],
  "test": []
}
```

### 6. 验证

```bash
python -m shell_agent validate-project
python -m shell_agent verify --sample data/beam2/meta/train_001.json --report build/verification/beam2-train-001.md
python -m shell_agent verify-dataset --development
```

## 完成接入后会得到什么

| 产物 | 来源 |
| --- | --- |
| `data/beam2/actual/*.csv` | 单元适配器 |
| 单样本报告 | `verify` |
| `build/verification/dataset-results.json` | `verify-dataset` |
| 编译与测试输出 | `build_command`、`test_command` |
| 规划和迭代记录 | 可选的 `replan`、`run` |

接入成功只表示流程可运行；是否达到数值目标，以独立测试集和验收阈值为准。

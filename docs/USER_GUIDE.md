# 通用单元矩阵工作流用户手册

## 用户需要提供什么

公共工作流不再把 `S4`、`4节点` 或 `24 x 24` 当成固定前提。使用一个新单元时，用户只维护三类输入：

1. `workflow/project.json` 中的单元类型、矩阵尺寸和适配器配置。
2. 一个包含 `train`、`validation`、`test` 三个互斥集合的数据集清单。
3. 每个样本的元数据、可信参考矩阵，以及适配器生成的实现矩阵。

现有 Abaqus S4 是第一个可运行示例，不是公共框架的类型限制。

## 最少配置

复制 `workflow/project.example.json` 的结构到 `workflow/project.json`，优先修改以下键：

```json
{
  "project_id": "my-element-stiffness",
  "element_type": "MY_ELEMENT",
  "matrix_dimensions": [8, 8],
  "dataset": "data/datasets/my_element.json",
  "primary_sample": "data/my_element/meta/train_001.json",
  "reference_generation_methods": ["external_solver"],
  "adapter": {
    "kind": "command"
  }
}
```

如果矩阵自由度可按节点组织，再填写：

```json
{
  "node_count": 4,
  "dof_labels_per_node": ["u", "v"],
  "diagnostic_groups": {
    "translation": ["u", "v"]
  }
}
```

`node_count * dof_labels_per_node` 的数量必须等于方阵尺寸。无法按节点组织时，可以省略这两个键，并在 `diagnostic_groups` 中直接填写从零开始的矩阵索引。

检查配置：

```bash
python -m shell_agent validate-project
```

## 适配器

工作流与数值内核之间使用适配器隔离。

### 内置 S4

```json
{"adapter": {"kind": "builtin_s4"}}
```

该适配器只对应当前仓库中的 `4节点 x 6自由度 = 24` C++ S4 内核。把矩阵尺寸改成其他值时必须切换到 `command` 适配器，框架不会假装同一套有限元公式适用于任意单元。

### 外部命令

```json
{
  "adapter": {
    "kind": "command",
    "build_command": ["cmake", "--build", "build"],
    "evaluate_command": ["build/my_element_cli", "{sample}"],
    "test_command": ["ctest", "--test-dir", "build", "--output-on-failure"]
  }
}
```

命令使用参数数组直接执行，不经过 shell。可用占位符为 `{root}`、`{project}`、`{sample}` 和 `{report}`。

`evaluate_command` 必须读取样本元数据并把实现矩阵写到 `implementation_matrix` 指定的位置。公共层随后按 `matrix_dimensions` 读取参考矩阵与实现矩阵，统一计算 Frobenius 相对误差、最大绝对误差、逐项最大相对误差和对称性误差。

## 样本与数据集

样本模板位于 `data/templates/sample-meta.example.json`。新样本至少包含：

- 唯一的 `sample_id`；
- 与项目配置一致的 `element_type`；
- 状态为 `real_abaqus_export` 或 `verified_external_reference` 的来源记录；
- `reference_matrix` 和 `implementation_matrix` 路径。

矩阵 CSV 不带表头，必须是配置声明的方阵尺寸，所有值有限，参考矩阵近似对称且不为空。

数据集模板位于 `data/templates/dataset.example.json`：

- `train` 可向 Planner、Theory 和 Developer 提供详细诊断；
- `validation` 用于候选筛选，避免只适配训练样本；
- `test` 是预先登记并锁定哈希的最终留出集。

登记样本：

```bash
python -m shell_agent register-sample \
  --meta data/my_element/meta/train_001.json \
  --split train
```

验证全部集合：

```bash
python -m shell_agent verify-dataset
python -m shell_agent verify-dataset --require-test
```

开发期只验证 train/validation，明确不读取锁定测试集：

```bash
python -m shell_agent verify-dataset --development
```

完整 Agent 候选门禁会自动采用这一开发范围；只要 validation 非空，候选就不得让验证集最差 Frobenius 误差超过配置中的 `max_validation_error_regression`。test 只在显式最终验收时读取。

## 规划重置

切换单元类型、矩阵尺寸、自由度契约或算法大方向时，不应让旧补丁记忆继续约束新项目。执行：

```bash
python -m shell_agent reset-plan \
  --reason "切换到新的单元类型和数据集"
```

该命令不会删除历史运行，而是把当前实验记忆、规划状态和最新报告复制到 `workflow/archive/`，然后建立空白规划代次。

只让 Planner 生成新计划，不调用 Theory、Developer 或 Reviewer，也不修改源码：

```bash
python -m shell_agent replan
```

计划保存在 `workflow/plans/replan-g代次-时间/experiment-plan.json`。确认计划后再运行完整闭环：

```bash
python -m shell_agent run --max-iterations 3
```

目标误差默认读取 `workflow/project.json` 的 `acceptance.target_error`。

## 协同边界

```mermaid
flowchart LR
    A["项目配置"] --> B["数据集与适配器校验"]
    B --> C["Planner 选择单一实验"]
    C --> D["Theory 论证机理"]
    D --> E["Developer 只改白名单源码"]
    E --> F["适配器生成实现矩阵"]
    F --> G["公共数值门禁"]
    G --> H["Reviewer 接受或拒绝"]
    H --> I["实验记忆与下一轮"]
```

这样划分的原因是：单元公式属于适配器，矩阵比较和数据治理属于公共层，模型建议不能控制验收门槛，测试集也不能参与自适应调参。更换单元时复用的是编排、数据协议、门禁、审计和回退机制，而不是错误复用某个单元的物理公式。

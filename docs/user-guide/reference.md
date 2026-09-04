# 文件与字段参考

本页用于查询，不要求从头阅读。

## 顶层目录

| 目录 | 内容 | 普通用户是否常改 |
| --- | --- | --- |
| `workflow/` | 项目配置、检查点、计划和实验记忆 | 主要修改 `project.json` |
| `data/` | 参考矩阵、实现矩阵、元数据和数据集 | 是 |
| `shell_agent/` | 统一 Python CLI 和公共验证逻辑 | 通常否 |
| `src/`、`include/` | 当前 S4 C++ 实现 | 开发单元公式时修改 |
| `elements/` | 推荐的新单元独立实现目录 | 接入新单元时创建 |
| `tests/` | Python 与当前 S4 测试 | 开发时修改 |
| `agents/` | 智能体角色提示词 | 通常否 |
| `scripts/` | 在线编排和 Abaqus 工具 | 工具开发时修改 |
| `docs/` | 用户、技术和验证文档 | 文档变更时修改 |
| `build/` | 可重新生成的编译与验证输出 | 不手工修改 |

## 项目配置字段

文件：`workflow/project.json`。

| 字段 | 含义 |
| --- | --- |
| `project_id` | 项目稳定标识，应与数据集一致 |
| `element_type` | 单元类型，应与样本元数据一致 |
| `matrix_dimensions` | 两个相等正整数，例如 `[24, 24]` |
| `node_count` | 可选节点数 |
| `dof_labels_per_node` | 每节点自由度名称；与节点数相乘后应等于矩阵尺寸 |
| `diagnostic_groups` | 用自由度名称或从零开始的索引定义误差分块 |
| `dataset` | 数据集清单路径 |
| `primary_sample` | 默认单样本验证入口 |
| `reference_generation_methods` | 允许的数据计划参考矩阵生成方法 |
| `adapter` | 数值实现接入方式 |
| `agent.allowed_patch_paths` | Developer 允许修改的源码白名单 |
| `agent.test_paths` | 相关测试路径 |
| `agent.experiment_classes` | Planner 可选择的实验类别 |
| `acceptance` | 误差目标和回归门槛 |

## 样本元数据的作用

样本元数据把“物理算例”和“两个矩阵文件”绑定在一起，解决三个问题：

1. 实现程序知道该计算什么；
2. 公共验证层知道去哪里读取参考和实现矩阵；
3. 结果可以追溯到求解器、作业和导出方法。

通用最小结构：

```json
{
  "sample_id": "train_001",
  "element_type": "MY_ELEMENT",
  "parameters": {},
  "reference_matrix_source": {
    "status": "verified_external_reference",
    "solver": "可信参考求解器",
    "job": "作业编号"
  },
  "reference_matrix": "data/my_element/reference/train_001.csv",
  "implementation_matrix": "data/my_element/actual/train_001.csv"
}
```

`reference_matrix_source.status` 只接受：

- `real_abaqus_export`；
- `verified_external_reference`。

当前 S4 历史样本可使用兼容字段 `abaqus_matrix_source`、`abaqus_matrix` 和 `cpp_matrix`。

## 数据集三个划分

| 划分 | 用途 | 开发阶段是否读取 |
| --- | --- | --- |
| `train` | 提供详细误差诊断，支持算法调整 | 是 |
| `validation` | 筛选候选，防止只适配训练样本 | 是 |
| `test` | 锁定后的最终留出验收 | 否，只有最终验收读取 |

三个数组必须存在且互不重叠。`test` 登记后由 `data/datasets/test-lock.json` 保存元数据和参考矩阵哈希。

## 适配器是什么

适配器是公共工作流与具体单元公式之间的边界。公共层只关心“给定样本，生成实现矩阵”；具体采用 C++、Python、外部程序或哪种有限元理论，由适配器负责。

### `builtin_s4`

- 只适用于当前四节点、每节点六自由度的 `24 x 24` S4 内核；
- 构建仓库内 C++ CLI；
- 生成 S4 实现矩阵并运行 Catch2 测试。

### `command`

- 用于非 S4 或非 `24 x 24` 单元；
- `build_command` 可选；
- `evaluate_command` 必填；
- `test_command` 可选；
- 命令以参数数组直接执行，不经过 shell。

## 命令速查

| 命令 | 作用 | 是否联网 |
| --- | --- | --- |
| `validate-project` | 校验项目配置和自由度映射 | 否 |
| `check` | 校验配置、依赖和 LangGraph 图 | 否 |
| `verify` | 构建适配器、验证一个样本并运行适配器测试 | 否 |
| `verify-dataset --development` | 验证 train 和 validation | 否 |
| `verify-dataset --require-test` | 最终严格验收 | 否 |
| `validate-data-plan` | 校验数据生成计划 | 否 |
| `register-sample` | 校验并登记可信样本 | 否 |
| `check-test-lock` | 检查测试集文件哈希 | 否 |
| `api-check` | 发送最小接口请求 | 是 |
| `reset-plan` | 归档当前代次并新建规划代次 | 否 |
| `replan` | 运行基线与 Planner | 是 |
| `run` | 启动完整 LangGraph 迭代 | 是 |
| `resume` | 从 SQLite 检查点恢复 | 是 |

## 统一数值指标

| 指标 | 含义 |
| --- | --- |
| `frobenius_relative_error` | 整体矩阵差异，当前主进度指标 |
| `max_absolute_error` | 任意条目的最大绝对差 |
| `max_relative_entry_error` | 逐项最大相对差，容易被参考矩阵近零条目放大 |
| `symmetry_error` | 实现矩阵相对自身转置的误差 |
| `<group>__<group>` | `diagnostic_groups` 产生的分块相对误差 |

## 文件生命周期

### 用户维护

- 项目配置；
- 样本元数据；
- 数据集清单；
- 可信参考矩阵及来源证据；
- 单元实现和测试。

### 工具生成

- 实现矩阵；
- `build/verification/` 下的报告、结果和二进制；
- `workflow/checkpoints/` 下的恢复状态；
- `workflow/runs/` 下的运行审计。

工具生成不等于可以随意覆盖：实现矩阵应由适配器重新生成，可信参考矩阵只能由外部可信来源更新。

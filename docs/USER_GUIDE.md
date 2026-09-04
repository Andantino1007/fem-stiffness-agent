# 通用单元矩阵工作流用户手册

本手册面向需要接入、运行或验证有限元单元矩阵的使用者。主路径只回答三件事：需要准备什么、执行什么命令、结果在哪里。算法推导和多智能体内部实现放在独立说明中。

## 先选择你的任务

| 目标 | 从这里开始 |
| --- | --- |
| 运行仓库现有的 Abaqus S4 示例 | [快速开始](user-guide/quickstart.md) |
| 给现有单元增加一个参考样本 | [接入新单元与新增样本](user-guide/add-new-element.md#只增加一个样本) |
| 接入梁、实体或其他非 24 x 24 单元 | [接入新单元与新增样本](user-guide/add-new-element.md#完整示例接入一个-6-x-6-梁单元) |
| 查某个目录、JSON 字段或输出文件 | [文件与字段参考](user-guide/reference.md) |
| 理解适配器、多智能体和数据集为什么这样设计 | [架构与协同](user-guide/architecture.md) |
| 命令失败或结果不符合预期 | [故障排查](user-guide/troubleshooting.md) |

## 用户视角的输入和输出

技术上的输入是单元物理信息和可信参考矩阵，技术上的输出是实现计算出的单元刚度矩阵及其验证报告。

### 必需输入

1. **项目配置**：单元类型、矩阵尺寸、自由度、数据集、适配器和验收阈值。
2. **样本元数据**：一个算例的几何、材料、自由度顺序及文件路径。
3. **可信参考矩阵**：由 Abaqus 或其他可追溯求解器导出的方阵 CSV。
4. **实现适配器**：读取样本并生成同尺寸实现矩阵的程序或命令。
5. **数据集清单**：把样本放入互不重叠的 `train`、`validation`、`test`。

### 主要输出

- 实现矩阵 CSV，例如 `data/cpp/s4_train_003_node_down_cpp.csv`；
- 单样本 Markdown 报告；
- `build/verification/dataset-results.json`；
- 编译产物和批量样本报告，默认位于 `build/verification/`；
- 在线迭代的计划、运行记录和检查点，位于 `workflow/` 的对应目录。

## 标准操作流程

### 1. 准备数据

- 填写 `workflow/project.json`；
- 创建样本元数据 JSON；
- 导入可信参考矩阵 CSV；
- 准备能生成实现矩阵的适配器；
- 在数据集清单中登记样本。

矩阵 CSV 不带表头，必须是项目配置声明的 `N x N` 方阵，且所有条目为有限数值。参考矩阵必须非零、近似对称并记录来源。

### 2. 执行验证

```bash
python -m shell_agent validate-project
python -m shell_agent verify --sample <样本元数据.json> --report build/verification/<报告名>.md
python -m shell_agent verify-dataset --development
```

开发阶段使用 `--development`，只读取 `train` 和 `validation`。最终验收才运行：

```bash
python -m shell_agent verify-dataset --require-test
```

### 3. 检查结果

至少确认：

- 命令退出码为 `0`；
- 实现矩阵尺寸正确、有限、非零；
- 报告中的 Frobenius 相对误差、最大绝对误差和对称性误差可读取；
- `train`、`validation`、`test` 没有重叠；
- 最终验收时测试集哈希锁有效。

## 换一个单元时通常改哪些文件

| 文件或目录 | 用户动作 |
| --- | --- |
| `workflow/project.json` | 修改单元类型、矩阵尺寸、自由度、适配器和验收设置 |
| `data/<element>/meta/*.json` | 新建样本元数据 |
| `data/<element>/reference/*.csv` | 放入可信参考矩阵 |
| `data/datasets/<element>.json` | 维护三个数据集划分 |
| `src/<element>/` 或独立实现目录 | 实现矩阵计算程序 |
| `tests/<element>_tests.*` | 增加物理与回归测试 |

公共框架通常不需要修改。非 S4 或非 `24 x 24` 单元使用 `command` 适配器，不要把 S4 公式硬改成“通用公式”。

## 哪些文件可以删除

| 类型 | 是否可删除 | 影响 |
| --- | --- | --- |
| `build/`、`__pycache__/`、`*.pyc` | 可以 | 下次运行重新生成 |
| `workflow/checkpoints/` | 谨慎 | 删除后不能恢复中断的在线运行 |
| `workflow/runs/`、`workflow/archive/`、`workflow/plans/` | 谨慎 | 不影响编译，但会丢失本地审计与计划历史 |
| Abaqus 临时文件，如 `.lck`、`.sta`、`.sim` | 作业结束后通常可以 | 先确认可追溯的 `.mtx`、CSV 和日志已保存 |
| 参考矩阵、样本元数据、数据集清单 | 不可以随意删除 | 样本将不可验证或不可追溯 |
| `.env` | 可以，但不要提交 | 删除后需要重新配置在线接口 |

## 当前 S4 示例

当前仓库配置是 `4 节点 x 每节点 6 自由度 = 24 x 24` 的 Abaqus S4 示例。它使用 `builtin_s4` 适配器；公共矩阵校验、数据集和命令适配器本身支持项目配置声明的任意方阵尺寸。

S4 的 Abaqus 导出步骤见 [导出 S4 刚度矩阵](abaqus/export-s4-stiffness.md)。当前数值状态见 [S4 多样本验证报告](verification/s4-multi-sample-abaqus-report.md)。

## 文档组织原则

本手册按常见技术文档分层组织：快速开始用于第一次成功运行；操作指南解决具体任务；参考页集中列出目录、字段和命令；架构页解释设计原因。用户操作文档不再混入实验过程记录，后者统一放在 `docs/verification/` 和 `workflow/`。

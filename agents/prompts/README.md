# Agent 提示词

本目录保存在线 LLM Agent 的提示词。历史验收提示词位于根目录，当前正式迭代提示词位于 `workflow/`。运行时由 Python 编排器读取。

## 文件规则

每个角色由一对 Markdown 文件组成：

- `<role>.system.md`：角色定位、职责边界、可靠性要求。
- `<role>.user.md`：当前任务和输出格式。

当前角色：

| 角色 | System Prompt | User Prompt |
| --- | --- | --- |
| 理论研究 | `theory-research.system.md` | `theory-research.user.md` |
| C++ 开发 | `developer.system.md` | `developer.user.md` |
| 综合评审 | `reviewer.system.md` | `reviewer.user.md` |

正式迭代角色：

| 角色 | System Prompt | User Prompt |
| --- | --- | --- |
| 实验规划 | `workflow/planner.system.md` | `workflow/planner.user.md` |
| 理论研究 | `workflow/theory.system.md` | `workflow/theory.user.md` |
| C++ 开发 | `workflow/developer.system.md` | `workflow/developer.user.md` |
| 数值评审 | `workflow/reviewer.system.md` | `workflow/reviewer.user.md` |

Experiment Planner 输出结构化 JSON，限定本轮 `experiment_class`、目标矩阵块、允许修改项、禁止修改项和预期指标。Theory 与 Developer 必须遵守该计划。

Plan 各字段的详细含义、验证边界和运行产物位置见上一级 [agents README](../README.md#experiment-plan)。

## 运行时上下文

每个 `*.user.md` 必须保留：

```text
{{CONTEXT}}
```

工作流会把共享状态、代码片段、报告和日志插入该位置。上下文来源由 Python 编排代码控制，提示词只负责解释任务和约束输出。

## 修改要求

- 使用中文 Markdown。
- 任务要求要具体、可检查，避免泛泛地要求“分析一下”。
- 不要求或泄露模型隐藏推理，只使用模型返回的可见分析结果。
- 不编造 Abaqus 内部算法、项目文件或测试结论。
- 修改后先运行 `python -m shell_agent check` 和 Python 单元测试，再运行对应在线阶段检查输出。

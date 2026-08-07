# agents

本目录保存多 Agent 的角色提示词。节点调度代码位于 `scripts/`，这里保存可独立编辑、可版本管理的角色内容。

## 阶段2角色

| 角色 | 提示词 | 作用 |
| --- | --- | --- |
| Theory Research Agent | `theory-research.*.md` | 输出 S4 理论口径和风险 |
| Developer Agent | `developer.*.md` | 分析当前 C++ 代码缺口 |
| Reviewer Agent | `reviewer.*.md` | 评审阶段2是否通过 |

## 正式迭代角色

| 角色 | 提示词 | 作用 |
| --- | --- | --- |
| Experiment Planner | `workflow/planner.*.md` | 根据矩阵诊断和实验记忆选择本轮唯一实验方向 |
| Theory Research Agent | `workflow/theory.*.md` | 围绕 Planner 计划完成理论论证 |
| Developer Agent | `workflow/developer.*.md` | 按 Planner 边界为 `ShellStiffness.cpp` 生成受限 unified diff |
| Reviewer Agent | `workflow/reviewer.*.md` | 根据测试和误差事实返回 accept/reject JSON |

API Preflight、Coordinator、Duplicate Gate、Test、Decision 和 Progress 是确定性工具节点。它们负责接口检查、状态初始化、重复补丁拦截、真实编译测试、接受门槛、回退和进度同步，不让 LLM 自行宣称测试通过。

## Experiment Plan

Planner 每次输出一个结构化实验计划：

```text
workflow/runs/<run-id>/iteration-XX/experiment-plan.json
```

| 字段 | 含义 | 下游用途 |
| --- | --- | --- |
| `hypothesis_id` | 本轮实验唯一编号 | 追踪实验和识别重复方向 |
| `experiment_class` | 实验物理类别 | 限定为膜内、弯曲、横向剪切、钻转、DOF 映射、局部坐标或积分 |
| `target_block` | 主要对齐的矩阵块或自由度通道 | Theory 和 Test 聚焦对应误差 |
| `mechanism` | 本轮待验证的单一误差机理 | Theory 据此完成理论论证 |
| `allowed_changes` | Developer 允许修改的公式和代码范围 | 防止修改范围失控 |
| `forbidden_changes` | 禁止触碰的模块及历史失败方案 | 防止混合实验和重复失败 |
| `expected_metrics` | 本轮重点观察的总体、分块和具体条目指标 | Reviewer 判断假设是否得到支持 |
| `difference_from_history` | 与最接近历史实验的实质差异和新证据 | 证明本轮不是换一种说法重复旧方案 |

`experiment-plan.json` 是该轮最后一次有效计划。若 Duplicate Gate 检测到补丁重复并触发重新规划，还会保留：

```text
experiment-plan-1.json
experiment-plan-2.json
experiment-plan-3.json
```

这些计划是待验证假设，不代表 Abaqus S4 的内部公式已经得到证明。只有真实 C++/Catch2 测试和 Abaqus 矩阵误差下降后，候选修改才可能被接受。

## 提示词约定

- `*.system.md`：身份、边界和禁止事项。
- `*.user.md`：本轮任务及 `{{CONTEXT}}` 注入位置。
- 提示词使用中文，不写 API Key 和本机绝对路径。
- Developer Agent 不得修改测试、阈值、基准数据和脚本。
- Reviewer 的接受意见不能绕过本地“测试通过且误差下降”门槛。
- Planner 读取跨运行实验记忆并把历史约束写入 Plan；Developer 和 Reviewer 读取最近实验摘要。
- Theory 必须遵守 Plan 中的历史差异和禁止事项，不自行更换实验类别。
- Planner、Theory 和 Developer 不得原样重复历史 `do_not_repeat` 机制。
- Reviewer 必须输出 `failure_mechanism`、`do_not_repeat` 和 `next_focus`。

修改提示词后必须重新运行对应在线工作流验证。

# 智能体角色与约束

本目录保存在线智能体的角色提示词。确定性的编译、矩阵比较、补丁校验、数据登记和接受门槛均由 Python 程序执行，不能由模型自行宣称通过。

## 数值优化角色

| 角色 | 提示词 | 职责 |
| --- | --- | --- |
| 实验规划智能体 | `prompts/workflow/planner.*.md` | 根据训练集诊断和历史实验选择唯一修改方向 |
| 理论研究智能体 | `prompts/workflow/theory.*.md` | 论证规划范围内的单一理论假设 |
| 开发智能体 | `prompts/workflow/developer.*.md` | 只为 `ShellStiffness.cpp` 生成受限统一差异补丁 |
| 评审智能体 | `prompts/workflow/reviewer.*.md` | 根据候选前后事实给出接受或拒绝建议 |

实验规划智能体输出结构化 JSON，至少包含实验类别、目标分块、唯一主指标、允许修改项、禁止修改项和预期指标。理论研究与开发智能体必须遵守该计划。

本地程序会再次检查：

- 补丁只能修改 `src/shell/ShellStiffness.cpp`；
- 测试和真实矩阵比较必须通过；
- 整体误差和主指标必须有实质改善；
- 对称性、最大绝对误差及非目标分块不得越过门槛；
- 评审建议不能绕过本地硬门槛。

## 数据生成角色

| 角色 | 提示词 | 职责 |
| --- | --- | --- |
| 数据集规划智能体 | `prompts/dataset/planner.system.md` | 设计具体样本批次和数据划分 |
| Abaqus 数据智能体 | `prompts/dataset/data-agent.system.md` | 按已批准计划生成输入并调用真实 Abaqus |
| 数据集校验智能体 | `prompts/dataset/validator.system.md` | 检查日志、元数据、矩阵和来源事实 |

数据生成还受到确定性门禁约束：计划必须先通过 `validate-data-plan`，真实产物必须通过 `register-sample`，最终测试集必须通过哈希锁校验。

## 运行产物

每次在线数值迭代写入：

```text
workflow/runs/<运行编号>/
├── state.json
├── summary.md
└── iteration-XX/
    ├── experiment-plan.json
    ├── theory-analysis.md
    ├── developer.patch
    ├── verification-candidate.log
    └── reviewer-response.md
```

这些文件记录计划、假设、补丁、验证事实和评审结论。计划只是待验证假设，只有本地测试、数值门槛和评审全部通过后，候选代码才会保留。

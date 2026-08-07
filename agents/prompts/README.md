# 智能体提示词

本目录中的提示词全部使用中文说明，程序要求的 JSON 字段名和统一差异协议保持英文标识，以保证机器解析稳定。

## 数值优化提示词

| 角色 | 系统提示词 | 用户提示词 |
| --- | --- | --- |
| 实验规划智能体 | `workflow/planner.system.md` | `workflow/planner.user.md` |
| 理论研究智能体 | `workflow/theory.system.md` | `workflow/theory.user.md` |
| 开发智能体 | `workflow/developer.system.md` | `workflow/developer.user.md` |
| 评审智能体 | `workflow/reviewer.system.md` | `workflow/reviewer.user.md` |

## 数据生成提示词

| 角色 | 系统提示词 |
| --- | --- |
| 数据集规划智能体 | `dataset/planner.system.md` |
| Abaqus 数据智能体 | `dataset/data-agent.system.md` |
| 数据集校验智能体 | `dataset/validator.system.md` |

## 维护要求

- 普通说明、约束、风险和输出要求使用中文；
- 不翻译程序依赖的 JSON 键、文件路径、命令和协议标记；
- 修改提示词后运行全部 Python 测试；
- 不允许通过提示词放宽本地测试、矩阵来源或数值接受门槛。

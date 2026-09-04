# 文档目录

本目录是通用单元矩阵工作流及当前 S4 示例的技术文档入口。

## 用户手册

- `USER_GUIDE.md`：按任务选择入口，并给出标准操作主流程。
- `user-guide/quickstart.md`：第一次运行现有 S4 验证。
- `user-guide/add-new-element.md`：新增样本或接入非 S4、非 `24 x 24` 单元。
- `user-guide/reference.md`：目录、配置字段、样本字段、命令和文件生命周期速查。
- `user-guide/troubleshooting.md`：按错误现象定位配置、矩阵、编译和数据集问题。
- `user-guide/architecture.md`：适配器、数据集和多智能体协同的设计说明。

用户文档采用“快速开始、操作指南、参考、原理说明”分层。可复验的数值结论仍放在 `verification/`，不与入门步骤混写。

## 需求与理论文档

- `requirements/requirement-2-technical-route.md`：整体技术路线。
- `requirements/requirement-2-current-plan-for-discussion.md`：老师讨论方案。
- `requirements/requirement-2-abaqus-s4-theory-baseline.md`：S4 理论口径。

## 智能体文档

- `agents/role-definitions.md`：角色定义。

## Abaqus 文档

- `abaqus/export-s4-stiffness.md`：S4 刚度矩阵导出流程。

## 验证文档

- `verification/sample-001-report.md`：主样本数值验证报告。
- `verification/s4-multi-sample-abaqus-report.md`：当前多样本验证汇总。

## 维护规则

- 每轮可验证进展同步当前验证报告。
- 讨论项标记“待确认”，不能写成已完成。
- 数值达到目标前不能表述为“算法验收通过”。

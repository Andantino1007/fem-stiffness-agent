# 项目进度与下一步

本文档集中维护通用单元矩阵工具流、当前 S4 适配器、自动迭代结果和下一步计划。项目安装与运行方式见根目录 `README.md`。

## 当前状态

截至 2026-08-26：

| 阶段 | 状态 | 当前结果 |
| --- | --- | --- |
| 通用配置与适配器层 | 已完成首版 | 单元类型、任意方阵尺寸、数据集、诊断分组和补丁白名单由配置驱动 |
| 通用矩阵与数据治理 | 已完成首版 | 任意尺寸方阵校验、三划分、参考来源校验和测试集哈希锁已接通 |
| Planner 代次重置 | 已完成 | 旧活动记忆已归档；40 条历史证据以只读教训进入新 Planner 上下文 |
| S4 内置适配器 | 进行中 | 主样本误差 `0.0595967`；面外翘曲 003 误差 `0.365536`，目标为 `0.01` |
| 泛化数据验收 | 部分就绪 | 训练 4 个、验证 1 个、测试 0 个；训练平均误差 `0.220593675` |

当前 S4 误差约为 `5.95967%`，已通过三轮真实 Agent 迭代从 `14.2174%` 连续下降，但尚未达到 `1%`。通用公共层不再限定 `24 x 24`；现有 C++ S4 公式只属于 `builtin_s4` 适配器。

<!-- AGENT_WORKFLOW_STATUS_START -->
### Agent 自动迭代状态

- 项目：`abaqus-s4-stiffness`
- 单元类型：`Abaqus S4`
- 矩阵尺寸：`24 x 24`
- 规划代次：`2`
- 状态：`planned`
- 基线误差：`0.0595967`
- 最新计划：`workflow/plans/replan-g2-20260819-113431/experiment-plan.json`
- 假设：`replan-g2-drilling-001`
<!-- AGENT_WORKFLOW_STATUS_END -->

## 下一步

1. 按新计划单独验证 drilling 离散构造，不再只做罚系数常量缩放。
2. 保持已接受的膜内中心剪切投影、`2/3` 横向剪切系数和 `2 x 2` 剪切积分。
3. 候选必须同时改善 `drilling__drilling` 和总体 Frobenius，并通过非目标分块回归门禁。
4. 补充预先锁定的 test 参考样本，并继续增加非共面 validation 覆盖。
5. 用 `workflow/project.example.json` 和 command 适配器接入一个非 `24 x 24` 示例内核，完成端到端烟雾验收。
6. S4 单样本误差依次压缩到 `5%`、`2%` 和 `1%` 后，再评价多样本泛化结果。

## 近期里程碑

### 2026-08-26：修正 003 为面外翘曲算例

- 节点 1 从错误的平面内 Y 下拉修正为 `(0,0,-4)`，到其余节点所在 `z=0` 平面距离为 `4`。
- Abaqus 2024 重新导出 576 条真实刚度矩阵条目；作业 0 errors、2 条输入警告。
- C++ 对非共面四边形使用中心等参切向量构造平均平面，003 新误差为 `0.365536`。
- 开发数据集训练平均误差为 `0.220593675`，最差样本仍为 003；验证集误差为 `0.209217`。
- Python 34 个测试以及 C++ 7 个测试用例、621 个断言全部通过。

### 2026-08-19：通用工具流与 Planner 新代次

- 新增 `workflow/project.json`，统一声明单元类型、矩阵尺寸、数据集、适配器和 Agent 边界。
- 公共矩阵读取、参考矩阵校验和误差诊断改为任意 `N x N` 方阵。
- 新增 `builtin_s4` 与 `command` 两类适配器；S4 物理公式不再等同于公共框架。
- 新增可归档的 `reset-plan` 和不会修改源码的 Planner-only `replan`。
- 规划代次重置为 `2`；活动实验为空，保留 40 条只读历史教训。
- 新计划：`workflow/plans/replan-g2-20260819-113431/experiment-plan.json`。

### 2026-07-24：Experiment Planner 首批三轮均产生有效下降

- Runtime：`openai:gpt-5.5`。
- 第1轮膜内 assumed-strain 投影：`0.142174 -> 0.0813914`。
- 第2轮横向剪切有效刚度调整：`0.0813914 -> 0.0683817`。
- 第3轮横向剪切 `2 x 2` 积分：`0.0683817 -> 0.0595967`。
- 三轮 C++/Catch2 均通过并由 Reviewer 接受，运行状态为 `iteration_limit_reached`。
- Theory 上下文由约 69 KB 压缩到约 15.5 KB，解决代理网关断开问题。

### 2026-07-23：阶段2在线验收通过

- Runtime：`openai:gpt-5.4-mini`。
- Coordinator、Theory Research、Abaqus Data、Developer、Test、Reviewer 全部通过。
- C++/Catch2 本地命令返回码为 `0`。
- 最终状态：`Failed agents: none`、`Warning agents: none`、`Ready for next step: True`。

### 2026-07-23：阶段3第一轮物理基线

- 用真实四节点 Reissner-Mindlin 壳替换阶段1占位刚度。
- 膜和弯曲采用 `2 x 2` Gauss 积分。
- 横向剪切采用中心点选择性减缩积分。
- 钻转采用 `alpha=0.0085` 罚刚度。
- 增加局部坐标构造、全局坐标变换、平面几何校验和材料校验。
- Catch2：6 个测试用例、43 个断言全部通过。
- Frobenius 相对误差：`1.000000 -> 0.142348`。

### 2026-07-23：多 Agent 首次有效迭代

- 在线运行 3 轮 Theory、Developer、Test、Reviewer 闭环。
- 前两轮被拒绝并自动回滚。
- 第3轮误差由 `0.142348` 降至 `0.142174`，修改被接受。
- 报告：`workflow/runs/stage3-20260723-095429/summary.md`。

### 2026-07-24：增加跨运行实验记忆

- 新增 `workflow/experiment-memory.json`，最多保留最近 100 轮实验。
- Theory、Developer、Reviewer 读取历史实验、误差变化、失败机理和禁止重复项。
- Reviewer 输出 `failure_mechanism`、`do_not_repeat` 和 `next_focus`。

### 2026-07-24：迁移到 LangGraph

- 使用 `StateGraph`、SQLite checkpointer 和节点级 RetryPolicy。
- API 故障暂停在当前节点，不消耗数值迭代次数。
- 候选测试后立即恢复，Reviewer 暂停时工作区保持上一有效版本。
- 图的第一个节点为 API Preflight。

### 2026-07-24：统一 Python CLI

- 主入口改为 `python -m shell_agent`。
- C++ 编译、矩阵生成和 Catch2 由 Python `subprocess` 驱动。
- 新增离线 `check` 和在线 `api-check`。
- 当前默认模型已切换为 `gpt-5.5`；真实网关检查响应为 `API_OK`。

### 2026-07-24：增加 Experiment Planner 与重复补丁硬闸门

- LangGraph 每轮入口由 Theory 改为 Experiment Planner。
- Planner 用结构化 JSON 指定实验类别、目标矩阵块、允许修改项和禁止修改项。
- Theory 负责论证 Planner 选定的方向，不再自行切换实验类别。
- Developer 后增加本地 Duplicate Gate，按实际增删代码生成语义指纹，忽略注释和 hunk 行号。
- 命中当前运行或跨运行失败补丁时不执行编译，最多退回 Planner 重新规划 3 次。
- 相关 Python 测试 14 个全部通过，LangGraph 14 个节点编译通过。

## 进度同步规则

每完成一轮可验证结果，更新：

1. 本文档中的当前状态、自动迭代状态和近期里程碑。
2. `docs/verification/progress-log.md` 的详细时间线。
3. 对应阶段的验证报告。
4. 接口或目录变化时更新对应分目录 README。

## 详细记录

| 内容 | 路径 |
| --- | --- |
| 完整时间线 | `docs/verification/progress-log.md` |
| 当前数值报告 | `docs/verification/sample-001-report.md` |
| 最新 Agent 报告 | `docs/verification/agent-latest.md` |
| 跨运行实验记忆 | `workflow/experiment-memory.json` |
| LangGraph 运行目录 | `workflow/runs/run-时间戳/` |

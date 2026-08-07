# 需求2 Agent 角色定义

本文档定义需求2的多 Agent 协作口径。当前阶段已经支持 OpenAI API 真实 Agent：Theory Research Agent、Developer Agent、Reviewer Agent 可以调用 OpenAI API；Abaqus Data Agent 和 Test Agent 保持确定性工具节点。

## 总体原则

- 每个 Agent 只负责一个清晰职责，不直接修改其他 Agent 的输出。
- 所有 Agent 通过共享状态文件交换信息，避免口头式上下文丢失。
- 每个 Agent 输出可检查的文件，包括摘要、日志、状态字段和待处理问题。
- Reviewer Agent 负责决定是否回退到前序节点，而不是由开发节点自己判断完成。

## 角色 1：Coordinator Agent

职责：
- 读取用户需求和当前阶段目标。
- 创建或更新共享状态。
- 按顺序调度理论研究、基准数据、开发、测试、评审节点。
- 汇总本轮产物位置。

输入：
- 阶段目标。
- 样本配置。
- 当前项目文件结构。

输出：
- `workflow/runs/<run_id>/state.json`
- 本轮流程日志。

## 角色 2：Theory Research Agent

职责：
- 梳理 Abaqus S4、ANSYS SHELL181、现有 Shell203 参考实现之间的差异。
- 输出本阶段需要固定的理论口径。
- 标记后续误差对齐时最可能影响 1% 指标的因素。

阶段 2 当前输出：
- OpenAI 理论分析摘要，或离线确定性理论检查摘要。
- 待确认理论项列表。

后续重点：
- 单元类型：S4 与 SHELL181/现有 Shell203 的理论差异。
- 膜、弯曲、剪切、钻转刚度处理。
- 积分方案与剪切锁定处理。
- 局部坐标系、节点顺序、自由度顺序。

## 角色 3：Abaqus Data Agent

职责：
- 生成或接收 Abaqus 输入文件。
- 导出单元刚度矩阵。
- 校验矩阵维度、节点顺序、自由度顺序、单位和样本元数据。

阶段 2 当前输出：
- 检查 `sample_001_abaqus_s4.csv` 是否为 24 x 24。
- 标记当前是否为真实 Abaqus 矩阵。

后续重点：
- 自动调用 Abaqus 或读取 Abaqus 输出。
- 将真实矩阵转换为统一 CSV。
- 维护 X 个样本的数据集。

## 角色 4：Developer Agent

职责：
- 维护 C++ 壳单元刚度矩阵实现。
- 根据输入参数生成 24 x 24 单刚。
- 保持接口稳定，供测试 Agent 和评审 Agent 调用。

阶段 2 当前输出：
- 调用阶段 1 C++ 闭环。
- 记录编译、运行、报告生成状态。
- OpenAI Developer Agent 根据代码、报告和日志生成开发分析。

后续重点：
- 将占位刚度替换为真实壳单元刚度。
- 复用或迁移现有 Shell203 参考代码。
- 保持输入输出格式与 Agent 流程一致。

## 角色 5：Test Agent

职责：
- 使用 Catch2 执行单元测试。
- 校验矩阵维度、对称性、误差指标和报告生成。
- 将测试结果写入共享状态。

阶段 2 当前输出：
- 复用 `python -m shell_agent verify` 中的 Catch2 测试。
- 提取是否通过。

后续重点：
- 增加真实 Abaqus 数据集测试。
- 增加误差阈值测试。
- 区分流程测试、数值测试和回归测试。

## 角色 6：Reviewer Agent

职责：
- 综合理论、数据、开发、测试结果。
- 判断本轮是否可进入下一阶段。
- 输出问题清单和下一轮任务。

阶段 2 当前输出：
- 生成 `review.md`。
- 在 OpenAI 模式下，由 Reviewer Agent 综合所有产物生成评审结论。
- 明确当前流程状态：已接入真实 Abaqus S4 基准矩阵，但 C++ 壳单元理论实现仍需阶段 3 替换。

后续重点：
- 若误差超过 1%，定位是数据口径问题、理论实现问题还是测试指标问题。
- 给出回退节点，例如回到 Theory、Abaqus Data 或 Developer。

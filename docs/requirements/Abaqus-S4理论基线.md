# Abaqus S4 理论口径确认

## 结论

本项目的理论实现以 **Abaqus S4 单元** 为主口径。ANSYS SHELL181 与现有 Shell203 代码只作为理论参考、实现借鉴和交叉验证材料，不再作为第一优先对齐目标。

## 为什么按 Abaqus S4

- 当前已经导出了真实 Abaqus S4 的 24 x 24 单刚矩阵，且阶段 1 / 阶段 2 流程已经能读取、比较和报告误差。
- 最终验收要求是 C++ 输出单刚与 Abaqus 给出的单刚误差控制在 1% 内，因此理论实现必须优先贴近 Abaqus S4。
- SHELL181 与 Abaqus S4 都是工程壳单元，但内部公式、积分策略、钻转刚度、剪切处理、默认稳定化等细节可能不同；若直接按 SHELL181 写，后续可能长期卡在误差对齐。

## Abaqus S4 官方口径摘要

- S4 是 4-node general-purpose shell，并考虑 finite membrane strains。
- S4、S4R 等三维常规壳单元在节点上使用 1-6 自由度，即 3 个平动 + 3 个转动自由度。
- Abaqus 通用常规壳单元可随厚度变化在厚壳横向剪切行为与薄壳离散 Kirchhoff 行为之间过渡。
- S4 属于 finite-strain shell element，可考虑 finite membrane strains 和大转动。
- S4 的结果输出包含膜力、弯矩、扭矩、横向剪切力、膜应变、横向剪切应变、曲率变化等壳单元关键量。
- Abaqus 文档说明三转动自由度壳在曲面节点处会涉及法向转动小刚度，即 drilling rotation 相关刚度需要作为误差对齐重点之一。

## 对项目实现的影响

后续 C++ 实现不应只写一个普通板壳刚度矩阵，而应围绕 Abaqus S4 基准逐项对齐：

1. 自由度顺序固定为每节点 `ux uy uz urx ury urz`。
2. 节点顺序固定为 1-2-3-4 逆时针。
3. 先以平面四边形、均匀厚度、各向同性线弹性、单层壳截面为最小闭环。
4. 单刚中至少要覆盖膜刚度、弯曲刚度、膜-弯耦合可能项、横向剪切刚度和钻转刚度。
5. 横向剪切刚度、钻转刚度、局部坐标方向、厚度积分/截面刚度，是后续误差从大到小的主要排查项。
6. 阶段 3 的误差对齐应以真实 Abaqus S4 CSV 为基准，不再使用占位矩阵。

## 多 Agent 分工调整

- Theory Research Agent：优先研究 Abaqus S4 文档和导出的刚度矩阵特征，SHELL181 只作为辅助参考。
- Abaqus Data Agent：维护 Abaqus S4 基准样本，记录 `MATRIX GENERATE -> X1.sim -> mtxasm -> STIF-1.mtx -> CSV` 的导出链路。
- Developer Agent：实现目标从“通用壳单元”收敛为“尽量复现 Abaqus S4 单元刚度”。
- Test Agent：以 Abaqus S4 CSV 为金标准，先做 Frobenius 相对误差，再补 max entry / symmetry / zero-pattern 等指标。
- Reviewer Agent：若误差超过 1%，优先判断是 Abaqus S4 理论口径、自由度映射、局部坐标、剪切/钻转刚度还是数值积分差异。

## 后续待确认

- 1% 指标采用 Frobenius 相对误差，还是最大相对项误差，或二者都要求。
- 是否允许 C++ 实现中加入 Abaqus 风格的经验/惩罚型 drilling stiffness。
- 首轮是否只对齐当前 1m x 1m 平面单元，还是同步扩展到多个几何样本。
- 是否固定 Abaqus S4，而暂不比较 S4R、SHELL181。

## 参考资料

- Abaqus docs: Choosing a shell element: https://abaqus-docs.mit.edu/2017/English/SIMACAEELMRefMap/simaelm-c-shellelem.htm
- Abaqus docs: Three-dimensional conventional shell element library: https://abaqus-docs.mit.edu/2017/English/SIMACAEELMRefMap/simaelm-r-shellgeneral.htm

## 当前执行状态

- Abaqus S4 真实 24 x 24 基准矩阵已导出并同步回项目。
- 阶段 1：流程跑通，真实基准下当前 C++ 占位实现 Frobenius relative error = 1。
- 阶段 2：多 Agent 工作流骨架跑通。
- 下一步：阶段 3 开始将 `S4Stiffness.cpp` 从占位实现替换为按 Abaqus S4 口径收敛的真实壳单元刚度实现。

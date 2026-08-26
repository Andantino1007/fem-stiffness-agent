# S4 刚度矩阵输入文件

本目录新增四个单 S4 单元的 `*MATRIX GENERATE` 算例。材料、厚度、节点顺序和自由度顺序均与 `sample_001` 基准一致。

| 划分 | 样本 | 几何 | 节点坐标 |
| --- | --- | --- | --- |
| train | `s4_train_001_trapezoid_far` | 一个节点沿 x 方向拉远的梯形 | `(0,0) (6,0) (2,1) (0,1)` |
| train | `s4_train_002_long_rectangle` | 长宽比 6:1 的长方形 | `(0,0) (6,0) (6,1) (0,1)` |
| train | `s4_train_003_node_down` | 节点 1 沿 Z 负方向拉到原平面下方，形成非共面翘曲四边形 | `(0,0,-4) (1,0,0) (1,1,0) (0,1,0)` |
| validation | `s4_validation_001_skew` | 独立保留的斜平行四边形 | `(0,0) (2.5,0) (3.25,1.25) (0.75,1.25)` |

对应数据计划为：

- `data/datasets/plans/s4_distorted_train_batch.json`
- `data/datasets/plans/s4_skew_validation_batch.json`

这些计划定义了目标划分，但在 Abaqus 矩阵真实导出并通过校验之前，不会提前写入 `data/datasets/shell_stiffness.json`。

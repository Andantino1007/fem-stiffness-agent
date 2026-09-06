# Abaqus 刚度矩阵

本目录中的 `sample_001_reference.csv` 和四个 `s4_*_reference.csv` 均为真实 Abaqus S4 基准刚度矩阵。

新增矩阵覆盖远点梯形、`6 x 1` 长方形、节点 1 沿 Z 负方向拉到原平面下方形成的非共面翘曲四边形，以及斜平行四边形。对应原始 `.mtx`、作业日志及解析条目数见 `data/reference/abaqus/raw_matrices/`、`data/reference/abaqus/logs/` 和各自元数据。

生成链路：

```text
sample_001_s4_matrix_export.inp
-> sample_001_s4_matrix_export_X1.sim
-> abaqus mtxasm job=sample_001_s4_matrix_export_X1 text
-> sample_001_s4_matrix_export_X1_STIF-1.mtx
-> scripts/abaqus/convert_abaqus_mtx_to_csv.py
-> sample_001_reference.csv
```

矩阵要求：

- 尺寸为 `24 x 24`。
- 节点顺序为 `1-2-3-4`。
- 每节点自由度顺序为 `x y z rx ry rz`。
- 矩阵应保持数值对称。
- 文件不包含表头。

该矩阵用于 C++ 误差比较、Catch2 测试和验证报告。当前 C++ 已使用真实壳单元物理实现，但仍未达到 `1%` 验收目标，不能宣称数值验收通过。

# Abaqus 刚度矩阵

`sample_001_abaqus_s4.csv` 是 `sample_001` 的真实 Abaqus S4 基准刚度矩阵。

生成链路：

```text
sample_001_s4_matrix_export.inp
-> sample_001_s4_matrix_export_X1.sim
-> abaqus mtxasm job=sample_001_s4_matrix_export_X1 text
-> sample_001_s4_matrix_export_X1_STIF-1.mtx
-> scripts/abaqus/convert_abaqus_mtx_to_csv.py
-> sample_001_abaqus_s4.csv
```

矩阵要求：

- 尺寸为 `24 x 24`。
- 节点顺序为 `1-2-3-4`。
- 每节点自由度顺序为 `x y z rx ry rz`。
- 矩阵应保持数值对称。
- 文件不包含表头。

该矩阵用于 C++ 误差比较、Catch2 测试和验证报告。当前 C++ 已使用真实壳单元物理实现，但仍未达到 `1%` 验收目标，不能宣称数值验收通过。

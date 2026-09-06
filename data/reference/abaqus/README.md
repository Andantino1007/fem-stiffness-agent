# Abaqus 数据

本目录保存 Abaqus S4 基准样本的输入、矩阵和元数据。

## 子目录

- `input_decks/`：Abaqus `.inp` 文件，包括普通模型、矩阵生成和反力法备用方案。
- `matrices/`：由 Abaqus 导出并转换得到的 `24 x 24` CSV。
- `metadata/`：节点、材料、厚度、自由度顺序和导出来源。
- `raw_matrices/`：Abaqus 直接导出的可追溯文本 `.mtx`。
- `logs/`：确认矩阵输出、分析完成和错误计数的精简 `.msg` 日志。

## 推荐导出方法

当前主方法是：

```text
MATRIX GENERATE
-> 直接生成 *_STIF1.mtx，或 X1.sim
-> 仅在没有文本矩阵时运行 abaqus mtxasm job=<X1作业名> text
-> *_STIF*.mtx
-> scripts/abaqus/convert_abaqus_mtx_to_csv.py
```

如果 Abaqus 版本或许可证环境无法使用 `mtxasm`，可使用 `sample_001_s4_reaction_export.inp` 和 ODB 反力提取脚本作为备用方法，但两种方法得到的数据必须分别标注来源。

详细操作见 `docs/abaqus/导出S4刚度矩阵.md`。

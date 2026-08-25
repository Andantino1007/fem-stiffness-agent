# 数据目录

本目录保存样本输入、可信参考矩阵、样本元数据和实现输出矩阵。公共契约支持项目配置声明的任意方阵尺寸；当前 `abaqus/` 和 `cpp/` 是 S4 示例数据。

## 目录结构

```text
data/
├── datasets/               训练集、验证集和测试集划分清单
├── templates/              通用样本元数据和数据集模板
├── abaqus/
│   ├── input/      Abaqus 输入文件
│   ├── matrix/     Abaqus 导出的 24 x 24 基准矩阵
│   └── meta/       样本参数与数据来源说明
└── cpp/            C++ 生成的 24 x 24 矩阵
```

## 当前样本

`sample_001` 是单位正方形平面 S4 单元：

- 节点顺序：`1-2-3-4` 逆时针。
- 每节点自由度：`x y z rx ry rz`。
- 全矩阵顺序：节点1的6个自由度，然后依次为节点2、节点3和节点4。
- 材料：各向同性线弹性，`E=2.1e11`，`nu=0.3`。
- 厚度：`0.01`。

## 样本契约

每个样本至少应包含：

```text
data/abaqus/input/<sample_id>_*.inp
data/abaqus/meta/<sample_id>.json
data/abaqus/matrix/<sample_id>_abaqus_s4.csv
data/cpp/<sample_id>_cpp.csv
```

当前 S4 示例矩阵 CSV 必须满足：

- 恰好 24 行、每行 24 个数值。
- 不带行名、列名和额外表头。
- 自由度顺序与元数据一致。
- Abaqus 与 C++ 使用相同单位制。
- 基准矩阵来源必须记录在对应元数据中。

其他单元的矩阵尺寸取自 `workflow/project.json` 的 `matrix_dimensions`，样本使用 `reference_matrix` 和 `implementation_matrix` 两个通用字段。完整格式见 `docs/USER_GUIDE.md` 和 `data/templates/`。

## 新增样本建议

新增样本时依次覆盖：平面规则四边形、斜平面四边形、轻微扭曲四边形、厚度变化、材料参数变化。先保证单个样本可复现，再扩展到批量 `X` 个样本。

不得仅替换 CSV 而不更新元数据，否则误差结果无法追溯。

## 训练集、验证集与测试集

划分清单位于 `data/datasets/shell_stiffness.json`。训练集用于智能体数值迭代，验证集用于候选筛选，锁定测试集只用于最终泛化验收。同一样本禁止同时进入多个集合。

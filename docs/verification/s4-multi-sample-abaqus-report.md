# S4 多样本 Abaqus 刚度矩阵验证报告

## 执行范围

- 基线提交：`60d469541c86cb4ced1a87cee42298a746df17fc`
- 参考求解器：Abaqus 2024
- 单元：单个 S4，4 节点，每节点 6 自由度
- 材料：`E=2.1e11`，`nu=0.3`
- 厚度：`0.01`
- 导出方法：`*MATRIX GENERATE` 和 `*MATRIX OUTPUT, STIFFNESS, FORMAT=COORDINATE`

本机 Abaqus 直接生成了完整坐标格式的 `*_STIF1.mtx`，未使用 `mtxasm`。原始矩阵同时包含上下三角条目；转换器已改为仅补齐缺失的对称项，避免重复累加完整矩阵的非对角项。

`s4_train_003_node_down` 已修正为：节点 1 沿 Z 负方向拉到原平面下方，形成非共面翘曲四边形。其坐标为 `(0,0,-4) (1,0,0) (1,1,0) (0,1,0)`，节点 1 到其余三节点所在 `z=0` 平面的距离为 `4`。

## Abaqus 来源

| 划分 | 样本 / Abaqus job | 原始矩阵 | 解析条目 | 作业结果 |
| --- | --- | --- | ---: | --- |
| train | `s4_train_001_trapezoid_far` | `data/abaqus/raw/s4_train_001_trapezoid_far_STIF1.mtx` | 376 | 完成，0 errors，1 条畸变输入警告 |
| train | `s4_train_002_long_rectangle` | `data/abaqus/raw/s4_train_002_long_rectangle_STIF1.mtx` | 372 | 完成，0 errors，0 warnings |
| train | `s4_train_003_node_down` | `data/abaqus/raw/s4_train_003_node_down_STIF1.mtx` | 576 | 完成，0 errors，2 条输入警告 |
| validation | `s4_validation_001_skew` | `data/abaqus/raw/s4_validation_001_skew_STIF1.mtx` | 380 | 完成，0 errors，0 warnings |

四个 CSV 均通过 `24 x 24`、有限值和对称性校验。003 的两条警告分别为等参角/质量畸变，以及平均单元法向与节点法向夹角超过 10 度的 curved/warped 警告；分析阶段为 0 warnings，作业正常完成。

## 数值结果

| 划分 | 样本 | Frobenius 相对误差 | 最大绝对误差 | 对称性误差 |
| --- | --- | ---: | ---: | ---: |
| train | `s4_train_001_trapezoid_far` | 0.339246 | 1.68835e+09 | 5.11124e-17 |
| train | `s4_train_002_long_rectangle` | 0.117996 | 4.38123e+08 | 1.42888e-17 |
| train | `s4_train_003_node_down` | 0.365536 | 8.66088e+08 | 1.0391e-16 |
| validation | `s4_validation_001_skew` | 0.209217 | 2.79829e+08 | 3.01256e-17 |

`verify-dataset --development` 对包含原始 `sample_001` 的完整训练集给出：4 个训练样本，平均 Frobenius 相对误差 `0.220593675`，最差样本为 `s4_train_003_node_down`，误差 `0.365536`。验证集已就绪，最差误差 `0.209217`。开发验证未读取 test；测试集仍为空，因此 `final_evaluation_ready=false`。本报告不宣称达到 `1%` 数值验收目标。

## 测试结果

- `python -m shell_agent check`：通过；项目配置、Python 3.13、LangGraph 1.2.11 和 SQLite checkpoint 3.1.1 均通过检查。
- `python -m shell_agent verify-dataset --development`：通过；训练 4 个、验证 1 个，明确跳过 test，结果写入 `build/verification/abaqus-s4-stiffness/dataset-results.json`。
- Python 工作流：`python -m unittest discover -s tests -p '*_tests.py' -v`，34 个测试通过。
- C++ 数值测试：Intel oneAPI 2025.1 `icx`，7 个测试用例、621 个断言全部通过；新增非共面翘曲矩阵的有限性、非零性和对称性回归。
- 转换器回归：完整对称矩阵不重复累加、三角矩阵自动补齐、不一致对称条目拒绝，3 个测试全部通过。

完整 Abaqus 作业证据保存在 `data/abaqus/evidence/`。003 的 `.msg` 和 `.dat` 日志记录了 `MATRIX OUTPUT FORMAT - COORDINATE`、两条输入警告、分析完成和 0 errors。

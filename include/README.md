# C++ 公共头文件

本目录保存项目自有 C++ 公共接口。当前 S4 专用头文件位于 `include/fem/s4/`，命名空间为 `fem::s4`。

| 文件 | 职责 |
| --- | --- |
| `fem/s4/Matrix24.hpp` | 固定大小 `24 x 24` 矩阵容器 |
| `fem/s4/S4ElementInput.hpp` | 节点、材料、厚度和矩阵路径输入 |
| `fem/s4/CsvMatrixIO.hpp` | `24 x 24` CSV 读写 |
| `fem/s4/MatrixCompare.hpp` | 弗罗贝尼乌斯、最大误差和对称性指标 |
| `fem/s4/S4Stiffness.hpp` | S4 单元总刚度和分量刚度入口 |

核心刚度接口：

```cpp
S4StiffnessComponents computeS4StiffnessComponents(const S4ElementInput& input);
Matrix24 computeS4Stiffness(const S4ElementInput& input);
```

`S4StiffnessComponents` 包含：

- `membrane`
- `bending`
- `shear`
- `drilling`
- `total`

公共接口应保持稳定，后续 MITC4 和 Abaqus 对齐工作优先在实现层迭代。

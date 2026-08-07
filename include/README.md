# include

本目录保存项目自有 C++ 公共接口，当前头文件位于 `include/shell/`，命名空间为 `shell`。

| 文件 | 职责 |
| --- | --- |
| `shell/Matrix24.hpp` | 固定大小 `24 x 24` 矩阵容器 |
| `shell/ShellElementInput.hpp` | 节点、材料、厚度和矩阵路径输入 |
| `shell/CsvMatrixIO.hpp` | `24 x 24` CSV 读写 |
| `shell/MatrixCompare.hpp` | Frobenius、最大误差和对称性指标 |
| `shell/ShellStiffness.hpp` | 壳单元总刚度和分量刚度入口 |

核心刚度接口：

```cpp
ShellStiffnessComponents computeShellElementStiffnessComponents(const ShellElementInput& input);
Matrix24 computeShellElementStiffness(const ShellElementInput& input);
```

`ShellStiffnessComponents` 包含：

- `membrane`
- `bending`
- `shear`
- `drilling`
- `total`

公共接口应保持稳定，后续 MITC4 和 Abaqus 对齐工作优先在实现层迭代。

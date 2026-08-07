# src

本目录保存项目自有 C++ 实现。

```text
src/
├── shell_stiffness_cli.cpp
└── shell/
    ├── Matrix24.cpp
    ├── ShellElementInput.cpp
    ├── CsvMatrixIO.cpp
    ├── MatrixCompare.cpp
    └── ShellStiffness.cpp
```

## 当前数据流

```text
sample JSON
-> 输入与几何校验
-> 局部坐标构造
-> 膜/弯曲/剪切/钻转分量积分
-> 全局坐标变换
-> 24 x 24 总刚度
-> Abaqus 比较与验证报告
```

## 当前物理实现

`ShellStiffness.cpp` 当前实现包括：

- 四节点 Reissner-Mindlin 壳物理基线。
- 膜、弯曲、剪切和钻转分量。
- 平面四边形局部坐标和全局转换。
- 正 Jacobian、材料参数和厚度校验。
- `2 x 2` 膜/弯曲积分和中心点减缩剪切积分。
- `alpha=0.0085` 钻转罚刚度。

当前 `sample_001` Frobenius 相对误差为 `0.142348`，尚未达到 `1%`。该实现仍缺少 Abaqus S4 对齐所需的 MITC4 剪切插值、钻转细化和更完整的畸变/曲面处理。

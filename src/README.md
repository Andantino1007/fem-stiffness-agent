# C++ 源代码

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
样本 JSON
-> 输入与几何校验
-> 局部坐标构造
-> 膜/弯曲/剪切/钻转分量积分
-> 全局坐标变换
-> 24 x 24 总刚度
-> Abaqus 比较与验证报告
```

## 当前物理实现

`ShellStiffness.cpp` 当前实现包括：

- 四节点赖斯纳－明德林壳物理基线。
- 膜、弯曲、剪切和钻转分量。
- 平面四边形局部坐标和全局转换。
- 正雅可比行列式、材料参数和厚度校验。
- `2×2` 膜、弯曲和横向剪切积分。
- `alpha=0.0085` 钻转罚刚度。

当前 `sample_001` 弗罗贝尼乌斯相对误差为 `0.0595967`，尚未达到 `1%`。当前实现仍需通过更多独立样本检验剪切、钻转、畸变和空间几何处理。

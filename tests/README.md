# 测试目录

本目录包含 C++ Catch2 测试和 Python 智能体及接口安全测试。

## C++ 数值测试

`s4_stiffness_tests.cpp` 当前有 7 个测试用例：

- 矩阵尺寸和误差可计算性。
- 总矩阵及四个物理分量的对称性。
- 刚度量级和有限数值。
- 弗罗贝尼乌斯相对误差小于 `0.2` 的基础回归门槛。
- 三方向刚体平移。
- 非共面翘曲四边形矩阵的有限性、非零性和对称性。
- 非法材料参数。

```bash
python -m stiffness_agent verify
```

## Python 工作流测试

- `model_api_client_tests.py`：两种接口格式、返回解析和 404 在线接口回退。
- `agents_tests.py`：补丁提取、路径白名单、危险调用拒绝、规划 JSON 校验和语义重复指纹。
- `graph_tests.py`：接口预检、重试分类、规划及重复门禁条件路由和图节点编译。

```bash
python -m unittest discover -s tests -p '*_tests.py'
```

Python 测试使用模拟对象，不调用真实在线接口。`tests/infra/` 是第三方 Catch2 源码，不做业务修改。

# tests

本目录包含 C++ Catch2 测试和 Python Agent/API 安全测试。

## C++ 数值测试

`shell_stiffness_tests.cpp` 当前有 6 个测试用例、43 个断言，覆盖：

- 矩阵尺寸和误差可计算性。
- 总矩阵及四个物理分量的对称性。
- 刚度量级和有限数值。
- Frobenius 误差小于 `0.2` 的阶段门槛。
- 三方向刚体平移。
- 非法材料参数。

```bash
python -m shell_agent verify
```

## Python 工作流测试

- `agent_openai_client_tests.py`：两种 API 格式、返回解析和 404 在线接口回退。
- `agents_tests.py`：补丁提取、路径白名单、危险调用拒绝、Planner JSON 校验和语义重复指纹。
- `graph_tests.py`：API Preflight、重试分类、Planner/重复闸门条件路由和图节点编译。

```bash
python -m unittest tests/shell_agent_cli_tests.py tests/agent_openai_client_tests.py tests/agents_tests.py tests/graph_tests.py
```

Python 测试使用 mock，不调用真实 API。`tests/infra/` 是第三方 Catch2 源码，不做业务修改。

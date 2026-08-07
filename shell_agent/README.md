# 统一命令行工具 `shell_agent`

项目统一 Python CLI，替代此前分散的 `.sh` 主入口。

## 命令

```bash
python -m shell_agent verify
python -m shell_agent verify-dataset
python -m shell_agent validate-data-plan data/datasets/plans/example_train_batch.json
python -m shell_agent register-sample --meta <meta.json> --split train
python -m shell_agent check-test-lock
python -m shell_agent check
python -m shell_agent api-check
python -m shell_agent run --max-iterations 3 --target-error 0.01
python -m shell_agent resume run-时间戳
python -m shell_agent legacy --max-iterations 3 --target-error 0.01
```

## 文件

| 文件 | 作用 |
| --- | --- |
| `__main__.py` | `python -m shell_agent` 模块入口 |
| `cli.py` | 子命令和参数解析 |
| `verification.py` | 直接调用 C++ 编译器、矩阵 CLI 和 Catch2 |
| `dataset_verification.py` | 训练集、验证集和测试集批量验证 |
| `dataset_plan.py` | 数据生成计划的确定性校验 |
| `dataset_registry.py` | 真实样本登记和测试集哈希锁 |

`verify` 不调用外层脚本，也不调用在线接口。`api-check` 发送一次最小真实请求。运行和恢复命令将控制权交给 LangGraph 编排，新的运行会先执行接口预检。

## 运行调用链

```text
python -m shell_agent run
-> __main__.py
-> cli.py
-> scripts/graph.py::main()
-> build_graph()
-> graph.stream()
```

节点、连接和条件分支均在 `scripts/graph.py` 的 `build_graph()` 中定义；各在线智能体的上下文组装和接口调用位于 `scripts/agents.py`。

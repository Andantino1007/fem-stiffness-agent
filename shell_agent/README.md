# shell_agent

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

`verify` 不调用 shell，也不调用在线 API。`api-check` 发送一次最小真实请求。`run` 和 `resume` 将控制权交给 LangGraph 编排，新的 run 会先执行 API Preflight。

## Run 调用链

```text
python -m shell_agent run
-> __main__.py
-> cli.py
-> scripts/graph.py::main()
-> build_graph()
-> graph.stream()
```

Node、Edge 和条件分支均在 `scripts/graph.py` 的 `build_graph()` 中定义；各在线 Agent 的上下文组装和 API 调用位于 `scripts/agents.py`。

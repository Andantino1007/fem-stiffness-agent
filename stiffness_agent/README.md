# 统一命令行工具 `stiffness_agent`

项目统一 Python CLI，负责项目配置、任意尺寸矩阵公共校验、适配器调度、数据集和 LangGraph 编排。

## 命令

```bash
python -m stiffness_agent verify
python -m stiffness_agent verify-dataset
python -m stiffness_agent validate-project
python -m stiffness_agent validate-data-plan data/datasets/plans/example_train_batch.json
python -m stiffness_agent register-sample --meta <meta.json> --split train
python -m stiffness_agent check-test-lock
python -m stiffness_agent check
python -m stiffness_agent api-check
python -m stiffness_agent reset-plan --reason "切换项目目标"
python -m stiffness_agent replan
python -m stiffness_agent run --max-iterations 3
python -m stiffness_agent resume run-时间戳
python -m stiffness_agent legacy --max-iterations 3 --target-error 0.01
```

## 文件

| 文件 | 作用 |
| --- | --- |
| `__main__.py` | `python -m stiffness_agent` 模块入口 |
| `cli.py` | 子命令和参数解析 |
| `project_config.py` | 项目配置与自由度分组校验 |
| `matrix_validation.py` | 任意尺寸方阵和公共误差指标 |
| `verification.py` | `builtin_s4` 与 `command` 适配器调度 |
| `planning_control.py` | 规划代次归档、重置和 Planner-only 运行 |
| `dataset_verification.py` | 训练集、验证集和测试集批量验证 |
| `dataset_plan.py` | 数据生成计划的确定性校验 |
| `dataset_registry.py` | 真实样本登记和测试集哈希锁 |

`verify` 不调用在线接口。`replan` 只调用接口预检和 Planner，不调用 Developer，也不修改源码。`run` 和 `resume` 将控制权交给 LangGraph 编排。

## 运行调用链

```text
python -m stiffness_agent run
-> __main__.py
-> cli.py
-> scripts/langgraph_workflow.py::main()
-> build_graph()
-> graph.stream()
```

节点、连接和条件分支均在 `scripts/langgraph_workflow.py` 的 `build_graph()` 中定义；各在线智能体的上下文组装和接口调用位于 `scripts/agent_workflow.py`。

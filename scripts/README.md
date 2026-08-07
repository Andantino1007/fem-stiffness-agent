# 脚本与编排程序

本目录保存在线接口客户端、多智能体编排和 Abaqus 数据工具。

项目推荐入口位于根目录 `shell_agent/`：

```bash
python -m shell_agent --help
```

本目录中的 `.sh` 仅用于兼容此前命令。

| 文件 | 用途 | 是否联网 |
| --- | --- | --- |
| `verify_shell_stiffness.sh` | 验证兼容入口，转发到 Python CLI | 否 |
| `run_agents.sh` | 双引擎兼容入口，非推荐方式 | 是 |
| `graph.py` | 默认 LangGraph 编排、检查点、重试和恢复 | 是 |
| `agents.py` | 智能体实现、提示词组装和公共工具 | 是 |
| `agent_openai_client.py` | OpenAI 兼容接口客户端 | 是 |

## 常用命令

单次数值验证：

```bash
python -m shell_agent verify
```

多智能体自动迭代：

```bash
python -m shell_agent run --max-iterations 3 --target-error 0.01
```

默认引擎为 `langgraph`。接口节点失败时退出码为 `3`，终端会打印恢复命令：

```bash
python -m shell_agent resume run-时间戳
```

仅检查环境和图编译，不调用在线接口：

```bash
python -m shell_agent check
```

发送最小真实请求检查在线接口：

```bash
python -m shell_agent api-check
```

LangGraph 运行命令会自动先执行同样的接口预检节点。

原手写编排仍可回退：

```bash
python -m shell_agent legacy --max-iterations 3 --target-error 0.01
```

正式自动迭代只允许开发智能体修改 `src/shell/ShellStiffness.cpp`。补丁先经过路径和危险调用校验，再经过 `git apply --check --recount`、C++/Catch2、真实 Abaqus 误差比较和评审决策。未改善时自动恢复。

退出码 `0` 表示至少接受一轮改进或已经达到目标；退出码 `2` 表示本批次没有改进被接受，候选代码已经回滚。

启动时会读取并补全 `workflow/experiment-memory.json`。每轮结束后记录理论摘要、补丁摘要、误差变化、失败机理、`do_not_repeat` 和下一步焦点，并在后续运行中注入在线智能体。

`OPENAI_API_STYLE=auto` 是在线接口格式回退，不是离线模式。

## Abaqus 工具

| 文件 | 用途 |
| --- | --- |
| `abaqus/convert_abaqus_mtx_to_csv.py` | 将 `.mtx` 转为 `24 x 24` CSV |
| `abaqus/generate_s4_reaction_export_inp.py` | 生成反力法 `.inp` |
| `abaqus/extract_reaction_stiffness_from_odb.py` | 从 ODB 反力恢复刚度矩阵 |

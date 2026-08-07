# workflow

本目录保存多 Agent 共享状态和运行产物。

## 长期实验记忆

`experiment-memory.json` 是跨 run 的持久化实验记忆，最多保留最近 100 轮。工作流会扫描新的 `runs/run-*/state.json`，并兼容读取历史 `runs/stage3-*/state.json`。

每条记录包含 Experiment Plan、修改前后误差、补丁指纹和测试状态、Reviewer 结论、失败机理、禁止重复项、下一步焦点、理论摘要和补丁摘要。Planner 读取跨运行记忆并负责选择不重复的实验方向，Developer 和 Reviewer 读取最近实验摘要。

## LangGraph Checkpoint

默认编排将节点状态保存在 `checkpoints/checkpoint.sqlite`。每个 run 使用唯一 `thread_id`，格式为 `run-YYYYMMDD-HHMMSS`。

API 节点超过重试次数时，运行退出并保留 checkpoint。执行 `--resume thread_id` 会从失败节点继续；已经成功的 Theory 或 Test 节点不会重新执行。基础设施错误不会计入数值实验记忆。

## 阶段2

```text
workflow/runs/stage2-latest/
├── state.json
├── theory_brief.md
├── abaqus_data_check.md
├── developer_log.txt
├── developer_agent_analysis.md
├── test_summary.md
└── review.md
```

## 自动迭代

每次运行创建独立时间戳目录：

```text
workflow/runs/run-YYYYMMDD-HHMMSS/
├── README.md
├── state.json
├── summary.md
├── verification-baseline.log
└── iteration-01/
    ├── ShellStiffness.cpp.before
    ├── experiment-planner-response.md
    ├── experiment-plan.json
    ├── theory-analysis.md
    ├── developer-response.md
    ├── developer.patch
    ├── duplicate-gate-1.json
    ├── patch-dry-run.log
    ├── patch-apply.log
    ├── verification-candidate.log
    └── reviewer-response.md
```

每个已整理的 run 可以包含自己的 `README.md`，作为该次运行的产物字典。阅读某次 run 时优先查看该文件和 `summary.md`；本页负责说明所有 run 通用的目录约定。

## 查看 Experiment Plan

每轮最终计划位于：

```bash
cat workflow/runs/<run-id>/iteration-01/experiment-plan.json
```

Planner 因重复补丁被退回时，每次规划会分别保存在 `experiment-plan-1.json`、`experiment-plan-2.json` 和 `experiment-plan-3.json`。字段解释见 [agents/README.md](../agents/README.md#experiment-plan)。

Duplicate Gate 在 Developer 后、编译测试前运行。它忽略注释和 diff 行号，按实际增删代码生成语义指纹；命中当前运行或跨运行历史失败补丁时，不执行编译，直接退回 Planner。单轮连续三次仍重复时记录为 `local_reject`。

被拒绝的补丁会恢复 `ShellStiffness.cpp.before`，并重新运行验证确保工作区回到上一有效状态。接受条件同时受 Reviewer 决策和本地误差下降门槛控制。

LangGraph 引擎在候选测试完成后就恢复源码；Reviewer 接受后再重新应用补丁并复验，因此 API 暂停期间不会把候选代码留在工作区。

`docs/verification/agent-latest.md` 保存最近一次自动迭代摘要，当前状态和里程碑同步到 `docs/PROJECT_PROGRESS.md`。

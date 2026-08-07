# 工作流状态与运行记录

本目录保存多智能体工作流的持久化状态、检查点和运行审计记录。

## 长期实验记忆

`experiment-memory.json` 最多保留最近一百轮实验的压缩记录，包括修改前后误差、补丁指纹、评审结论、失败机理、禁止重复项、下一步焦点和候选分块误差。

实验规划智能体读取近期记忆，避免重复已被证伪的补丁。被接受和被拒绝的实验都会记录，但只有经过本地硬门槛与评审的补丁才会保留在源码中。

## LangGraph 检查点

默认编排将节点状态保存在 `checkpoints/checkpoint.sqlite`。每次运行使用唯一线程编号，格式为 `run-YYYYMMDD-HHMMSS`。

接口节点超过重试次数后会暂停并保存检查点。恢复命令：

```bash
python -m shell_agent resume <运行编号>
```

恢复时从未完成节点继续，已经成功的节点不会重复执行。基础设施错误不计入数值实验记忆。

## 新运行目录

```text
workflow/runs/run-YYYYMMDD-HHMMSS/
├── state.json                         状态快照
├── summary.md                         中文汇总
├── verification-baseline.log          基线验证日志
└── iteration-01/
    ├── ShellStiffness.cpp.before      修改前源码备份
    ├── experiment-plan.json           实验计划
    ├── theory-analysis.md              理论分析
    ├── developer.patch                候选补丁
    ├── duplicate-gate-1.json          重复补丁检查
    ├── patch-dry-run.log              补丁预检日志
    ├── patch-apply.log                补丁应用日志
    ├── verification-candidate.log     候选验证日志
    └── reviewer-response.md           评审结果
```

历史 `stage*` 目录只作为已有运行记录保留，新代码不再生成这种命名。

## 补丁安全流程

1. 开发智能体只生成统一差异补丁；
2. 重复门禁按实际增删代码计算语义指纹；
3. 候选补丁通过预检后才会应用；
4. 编译和测试完成后立即恢复上一有效源码；
5. 本地数值门槛与评审均接受后，再次应用补丁并复验；
6. 任何失败都会保留日志和恢复有效版本。

这套顺序保证接口暂停或评审等待期间不会把未经接受的候选代码留在工作区。

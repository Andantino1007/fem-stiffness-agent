# 故障排查

先按终端中最早出现的错误定位。后续错误通常只是前一个问题的连锁结果。

## `validate-project` 拒绝项目配置

运行：

```bash
python -m shell_agent validate-project
```

常见原因：

| 提示 | 检查项 |
| --- | --- |
| `matrix_dimensions` 非法 | 必须是两个相等的正整数，例如 `[6, 6]` |
| 自由度数量不一致 | `node_count * len(dof_labels_per_node)` 必须等于矩阵尺寸 |
| 未知自由度名称 | `diagnostic_groups` 中的名称必须出现在 `dof_labels_per_node` |
| `builtin_s4` 尺寸不匹配 | 该适配器只接受 4 节点、每节点 6 自由度和 `24 x 24`；其他单元改用 `command` |
| 缺少 Agent 字段 | 补全 `allowed_patch_paths` 和 `experiment_classes` |

可从 `workflow/project.example.json` 复制完整结构，再逐项修改。

## 找不到编译器或适配器命令

如果出现 `Command not found`：

1. 确认命令能在当前终端直接运行；
2. 确认编译器、CMake 或外部程序已经加入 `PATH`；
3. 内置 S4 默认调用 `c++`，并传入 GCC/Clang 风格参数；需要时把 `CXX` 设为 `g++`、`clang++` 或其完整路径；
4. `command` 适配器的命令是 JSON 字符串数组，不支持 `&&`、管道或 shell 内建语法；
5. Windows 可执行文件路径建议写入 `evaluate_command`，不要依赖当前目录猜测。

示例：

```powershell
$env:CXX = "g++"
python -m shell_agent verify
```

当前不能把 MSVC 的 `cl.exe` 直接设为 `CXX`，因为验证驱动传入的命令行参数格式不同。仓库的 CMake 目标可以单独使用 MSVC 构建；源文件含中文注释时需启用 `/utf-8`。这种独立构建可检查 C++ 源码和测试，但不会替代 `shell_agent verify` 的矩阵生成与报告流程。

## 参考矩阵被拒绝

`register-sample` 会在登记前检查可信来源和矩阵内容。确认：

- 元数据的 `element_type` 与 `workflow/project.json` 一致；
- `reference_matrix_source.status` 是 `real_abaqus_export` 或 `verified_external_reference`；
- `reference_matrix` 指向实际存在的 CSV；
- CSV 无表头，恰好为配置声明的 `N x N`；
- 所有条目有限、矩阵非零且近似对称；
- `sample_id` 和元数据路径尚未登记到其他划分。

真实 Abaqus S4 导出问题见 [导出 S4 刚度矩阵](../abaqus/export-s4-stiffness.md)。不要用待验证实现生成的矩阵冒充参考矩阵。

## 实现矩阵不存在或尺寸不对

对于 `command` 适配器，`evaluate_command` 必须：

1. 读取 `{sample}` 指向的元数据；
2. 生成实现矩阵；
3. 写入 `implementation_matrix` 指定的路径；
4. 成功时返回退出码 `0`。

如果命令成功但验证仍提示找不到文件，重点检查元数据路径、工作目录和程序是否写到了另一个相对目录。矩阵必须是无表头、有限数值的 `N x N` CSV。

## 数据集验证失败

| 现象 | 处理 |
| --- | --- |
| `train` 为空 | 至少登记一个训练样本 |
| 三个划分重叠 | 每个元数据路径只能出现一次 |
| 样本文件不存在 | 修正数据集中的仓库相对路径 |
| `--development` 看不到 test | 这是预期行为；开发模式明确跳过 test |
| `--require-test` 返回失败 | 补充 validation、test，并确保 `test-lock.json` 与当前文件哈希一致 |
| 测试集锁失效 | 确认变更合理后重新登记测试样本或重建锁，不要绕过哈希检查 |

批量结果默认写入 `build/verification/dataset-results.json`。先查看失败样本对应的 `build/verification/dataset-reports/<split>/` 报告。

## Windows 命令换行失败

文档中的反斜杠续行适用于 Bash。PowerShell 最稳妥的写法是一行命令：

```powershell
python -m shell_agent verify --sample data/abaqus/meta/sample_001.json --report build/verification/sample_001-report.md
```

CMD 使用 `^`，PowerShell 使用反引号；不要把 Bash 的 `\` 原样复制到 CMD 或 PowerShell。

## 在线多智能体命令失败

`validate-project`、`check`、`verify` 和 `verify-dataset` 不需要在线模型。先让这些离线命令通过，再检查在线部分：

```bash
python -m shell_agent api-check
```

确认 `.env` 中的接口地址、模型名和密钥有效。`.env` 只保留在本机，不能提交到 Git。

## 哪些输出可以重建

可以删除并重新生成：`build/`、`__pycache__/` 和 `*.pyc`。

谨慎删除：`workflow/checkpoints/`、`workflow/runs/`、`workflow/archive/` 和 `workflow/plans/`，因为它们包含恢复状态或审计历史。

不要把参考矩阵、样本元数据或来源证据当作缓存删除。Abaqus 临时文件只有在 `.mtx`、CSV 和必要日志已经归档后才清理。

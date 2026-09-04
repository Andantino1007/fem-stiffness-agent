# 快速开始

本页目标是在不修改算法的前提下，完成一次现有 S4 样本验证并找到结果。

## 前置条件

- Python 3.10 或更高版本；
- 运行内置 S4 验证时，需要能以 `c++` 命令调用并接受 GCC/Clang 风格参数的 C++17 编译器；Windows 可使用 MinGW `g++` 或 LLVM `clang++`，并通过 `CXX` 指定；
- 仓库已克隆并位于仓库根目录；
- 仅运行离线验证时不需要 OpenAI 密钥；
- 重新生成 Abaqus 参考矩阵时才需要 Abaqus。

安装 Python 依赖：

```bash
python -m pip install -r requirements-langgraph.txt
```

## 第一步：检查环境

```bash
python -m shell_agent check
```

成功输出应包含项目名称、单元类型、矩阵尺寸、适配器，以及 `Project configuration passed` 和 `LangGraph environment check passed`。

如果只想检查项目 JSON，不检查 LangGraph：

```bash
python -m shell_agent validate-project
```

## 第二步：验证一个样本

为了避免覆盖仓库中的长期报告，把临时报告写到 `build/`：

```bash
python -m shell_agent verify \
  --sample data/abaqus/meta/sample_001.json \
  --report build/verification/sample_001-report.md
```

Windows PowerShell 可以写成一行：

```powershell
python -m shell_agent verify --sample data/abaqus/meta/sample_001.json --report build/verification/sample_001-report.md
```

该命令会：

1. 构建当前适配器；
2. 根据样本元数据生成实现矩阵；
3. 与可信参考矩阵比较；
4. 运行适配器测试；
5. 写出单样本报告。

在 macOS 上使用 `clang++` 时，不同编译器的浮点末位可能使已跟踪的
`data/cpp/*.csv` 实现矩阵显示为已修改。验证后先运行
`git diff -- data/cpp`，确认差异只来自本次生成的实现矩阵；不要把这类
生成差异作为文档修改提交，也不要改动 `data/abaqus/matrix/` 中的参考矩阵。
具体处理见 [故障排查](troubleshooting.md#macosclang-验证后实现矩阵显示为已修改)。

## 第三步：验证开发数据集

```bash
python -m shell_agent verify-dataset --development
```

该命令读取 `train` 和 `validation`，不会读取锁定的 `test`。默认结果位于：

```text
build/verification/dataset-results.json
```

每个样本的报告位于：

```text
build/verification/dataset-reports/<split>/<sample_id>.md
```

## 如何判断成功

- 终端显示 `Element matrix verification completed` 或 `Dataset verification completed`；
- 实现矩阵已经写入样本元数据指定的路径；
- 报告包含四个统一指标；
- 适配器测试通过；
- `dataset-results.json` 中的样本数和数据集清单一致。

## 下一步

- 只增加一个算例：见 [只增加一个样本](add-new-element.md#只增加一个样本)。
- 接入其他单元：见 [完整示例：接入一个 6 x 6 梁单元](add-new-element.md#完整示例接入一个-6-x-6-梁单元)。
- 命令失败：见 [故障排查](troubleshooting.md)。

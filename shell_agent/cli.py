"""项目统一 Python 命令行入口。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .api_check import perform_api_check, print_api_check
from .verification import DEFAULT_REPORT, ROOT, run_verification
from .dataset_verification import DEFAULT_DATASET, DEFAULT_DATASET_RESULT, run_dataset_verification
from .dataset_plan import validate_dataset_plan_command
from .dataset_registry import (
    DEFAULT_TEST_LOCK,
    check_test_lock_command,
    register_sample_command,
)


SCRIPTS_DIR = ROOT / "scripts"


def load_langgraph_main():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    from graph import main as langgraph_main

    return langgraph_main


def run_legacy(arguments: list[str]) -> int:
    command = [sys.executable, str(SCRIPTS_DIR / "agents.py"), *arguments]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m shell_agent",
        description="需求2壳单元刚度矩阵多 Agent 工作流。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="编译 C++、生成矩阵并运行 Catch2。")
    verify.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT.relative_to(ROOT),
        help="验证报告路径。",
    )

    verify_dataset = subparsers.add_parser(
        "verify-dataset", help="编译一次并验证训练集和测试集。"
    )
    verify_dataset.add_argument(
        "--dataset", type=Path, default=DEFAULT_DATASET.relative_to(ROOT)
    )

    validate_plan = subparsers.add_parser(
        "validate-data-plan", help="在调用 Abaqus 前校验 Dataset Planner 计划。"
    )
    validate_plan.add_argument("plan", type=Path)
    validate_plan.add_argument(
        "--dataset", type=Path, default=DEFAULT_DATASET.relative_to(ROOT)
    )

    register = subparsers.add_parser(
        "register-sample", help="验证真实 Abaqus 产物并登记到数据集。"
    )
    register.add_argument("--meta", type=Path, required=True)
    register.add_argument("--split", choices=("train", "validation", "test"), required=True)
    register.add_argument(
        "--dataset", type=Path, default=DEFAULT_DATASET.relative_to(ROOT)
    )

    check_lock = subparsers.add_parser(
        "check-test-lock", help="检查锁定测试集的清单和文件哈希。"
    )
    check_lock.add_argument(
        "--dataset", type=Path, default=DEFAULT_DATASET.relative_to(ROOT)
    )
    check_lock.add_argument(
        "--lock", type=Path, default=DEFAULT_TEST_LOCK.relative_to(ROOT)
    )
    verify_dataset.add_argument(
        "--result", type=Path, default=DEFAULT_DATASET_RESULT.relative_to(ROOT)
    )
    verify_dataset.add_argument(
        "--require-test", action="store_true", help="测试集为空时返回失败。"
    )

    subparsers.add_parser("check", help="检查 LangGraph 环境，不调用 API。")
    subparsers.add_parser("api-check", help="发送最小在线请求，检查 API、模型和网关。")

    run = subparsers.add_parser("run", help="启动 LangGraph 多 Agent 数值迭代。")
    run.add_argument("--max-iterations", type=int, default=3)
    run.add_argument("--target-error", type=float, default=0.01)

    resume = subparsers.add_parser("resume", help="从 SQLite checkpoint 恢复。")
    resume.add_argument("run_id")

    legacy = subparsers.add_parser("legacy", help="运行原手写编排。")
    legacy.add_argument("--max-iterations", type=int, default=3)
    legacy.add_argument("--target-error", type=float, default=0.01)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "verify":
        return run_verification(args.report)
    if args.command == "verify-dataset":
        return run_dataset_verification(args.dataset, args.result, args.require_test)
    if args.command == "validate-data-plan":
        return validate_dataset_plan_command(args.plan, args.dataset)
    if args.command == "register-sample":
        return register_sample_command(args.meta, args.split, args.dataset)
    if args.command == "check-test-lock":
        return check_test_lock_command(args.dataset, args.lock)
    if args.command == "check":
        return load_langgraph_main()(["--check"])
    if args.command == "api-check":
        print_api_check(perform_api_check())
        return 0
    if args.command == "run":
        return load_langgraph_main()(
            [
                "--max-iterations",
                str(args.max_iterations),
                "--target-error",
                str(args.target_error),
            ]
        )
    if args.command == "resume":
        return load_langgraph_main()(["--resume", args.run_id])
    if args.command == "legacy":
        return run_legacy(
            [
                "--max-iterations",
                str(args.max_iterations),
                "--target-error",
                str(args.target_error),
            ]
        )
    parser.error(f"未知命令：{args.command}")
    return 64

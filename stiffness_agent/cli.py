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
from .planning_control import replan_command, reset_planning_command
from .project_config import (
    DEFAULT_PROJECT_PATH,
    load_project_config,
    project_config_command,
)
from .dataset_registry import (
    DEFAULT_TEST_LOCK,
    check_test_lock_command,
    register_sample_command,
)


SCRIPTS_DIR = ROOT / "scripts"


def load_langgraph_main():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    from langgraph_workflow import main as langgraph_main

    return langgraph_main


def run_legacy(arguments: list[str]) -> int:
    command = [sys.executable, str(SCRIPTS_DIR / "agent_workflow.py"), *arguments]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m stiffness_agent",
        description="配置驱动的通用单元矩阵多 Agent 工作流。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="构建适配器、生成主样本矩阵并运行测试。")
    verify.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT.relative_to(ROOT),
        help="验证报告路径。",
    )
    verify.add_argument("--project", type=Path, default=DEFAULT_PROJECT_PATH.relative_to(ROOT))
    verify.add_argument("--sample", type=Path, help="覆盖项目配置中的主样本路径。")

    verify_dataset = subparsers.add_parser(
        "verify-dataset", help="构建一次适配器并验证三个数据集划分。"
    )
    verify_dataset.add_argument(
        "--dataset", type=Path, default=DEFAULT_DATASET.relative_to(ROOT)
    )
    verify_dataset.add_argument(
        "--project", type=Path, default=DEFAULT_PROJECT_PATH.relative_to(ROOT)
    )

    validate_plan = subparsers.add_parser(
        "validate-data-plan", help="在调用参考求解器前校验 Dataset Planner 计划。"
    )
    validate_plan.add_argument("plan", type=Path)
    validate_plan.add_argument(
        "--dataset", type=Path, default=DEFAULT_DATASET.relative_to(ROOT)
    )

    register = subparsers.add_parser(
        "register-sample", help="验证可信参考产物并登记到数据集。"
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
    verify_dataset.add_argument(
        "--development",
        action="store_true",
        help="只验证 train/validation，绝不读取锁定 test。",
    )

    subparsers.add_parser("validate-project", help="校验项目配置和适配器声明。")
    subparsers.add_parser("check", help="检查项目配置和 LangGraph 环境，不调用 API。")
    subparsers.add_parser("api-check", help="发送最小在线请求，检查 API、模型和网关。")
    reset_plan = subparsers.add_parser(
        "reset-plan", help="归档活动规划记忆并开启新的规划代次。"
    )
    reset_plan.add_argument("--reason", required=True, help="本次规划重置原因。")
    subparsers.add_parser("replan", help="只运行基线和 Planner，不修改实现源码。")

    run = subparsers.add_parser("run", help="启动 LangGraph 多 Agent 数值迭代。")
    run.add_argument("--max-iterations", type=int, default=3)
    run.add_argument("--target-error", type=float)

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
        return run_verification(args.report, args.project, args.sample)
    if args.command == "verify-dataset":
        if args.development and args.require_test:
            parser.error("--development 与 --require-test 不能同时使用")
        return run_dataset_verification(
            args.dataset,
            args.result,
            args.require_test,
            args.project,
            args.development,
        )
    if args.command == "validate-data-plan":
        return validate_dataset_plan_command(args.plan, args.dataset)
    if args.command == "register-sample":
        return register_sample_command(args.meta, args.split, args.dataset)
    if args.command == "check-test-lock":
        return check_test_lock_command(args.dataset, args.lock)
    if args.command == "validate-project":
        return project_config_command()
    if args.command == "check":
        code = project_config_command()
        if code != 0:
            return code
        return load_langgraph_main()(["--check"])
    if args.command == "api-check":
        print_api_check(perform_api_check())
        return 0
    if args.command == "reset-plan":
        return reset_planning_command(args.reason)
    if args.command == "replan":
        return replan_command()
    if args.command == "run":
        target_error = args.target_error
        if target_error is None:
            target_error = load_project_config().acceptance["target_error"]
        return load_langgraph_main()(
            [
                "--max-iterations",
                str(args.max_iterations),
                "--target-error",
                str(target_error),
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

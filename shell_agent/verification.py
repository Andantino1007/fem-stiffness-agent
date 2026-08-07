"""C++ 壳单元编译、矩阵生成和 Catch2 验证驱动。"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build" / "verification"
DEFAULT_REPORT = ROOT / "docs" / "verification" / "sample-001-report.md"
SAMPLE_PATH = ROOT / "data" / "abaqus" / "meta" / "sample_001.json"

SHELL_SOURCES = [
    ROOT / "src" / "shell" / "CsvMatrixIO.cpp",
    ROOT / "src" / "shell" / "Matrix24.cpp",
    ROOT / "src" / "shell" / "MatrixCompare.cpp",
    ROOT / "src" / "shell" / "ShellElementInput.cpp",
    ROOT / "src" / "shell" / "ShellStiffness.cpp",
]


def executable_path(name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return BUILD_DIR / f"{name}{suffix}"


def display_command(command: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def run_checked(command: list[str]) -> int:
    print(f"$ {display_command(command)}", flush=True)
    try:
        result = subprocess.run(command, cwd=ROOT, check=False)
    except FileNotFoundError as exc:
        print(f"Command not found: {command[0]}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 127
    return result.returncode


def compiler_command() -> list[str]:
    configured = os.getenv("CXX", "c++").strip()
    return shlex.split(configured) if configured else ["c++"]


def compiler_flags() -> list[str]:
    flags = ["-std=c++17", "-Wall", "-Wextra", "-pedantic", "-Iinclude"]
    configured = os.getenv("CXXFLAGS", "").strip()
    if configured:
        flags.extend(shlex.split(configured))
    return flags


def compile_verification_binaries() -> tuple[int, Path, Path]:
    """编译矩阵 CLI 和 Catch2 测试程序。"""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    cli_path = executable_path("shell_stiffness_cli")
    tests_path = executable_path("shell_stiffness_tests")
    compiler = compiler_command()
    flags = compiler_flags()
    source_args = [str(path.relative_to(ROOT)) for path in SHELL_SOURCES]

    compile_cli = [
        *compiler,
        *flags,
        *source_args,
        "src/shell_stiffness_cli.cpp",
        "-o",
        str(cli_path.relative_to(ROOT)),
    ]
    code = run_checked(compile_cli)
    if code != 0:
        return code, cli_path, tests_path

    compile_tests = [
        *compiler,
        *flags,
        "-Itests",
        *source_args,
        "tests/infra/catch.cpp",
        "tests/shell_stiffness_tests.cpp",
        "-o",
        str(tests_path.relative_to(ROOT)),
    ]
    code = run_checked(compile_tests)
    return code, cli_path, tests_path


def run_verification(report_path: Path = DEFAULT_REPORT) -> int:
    """编译并运行矩阵 CLI 和 Catch2，返回进程退出码。"""
    code, cli_path, tests_path = compile_verification_binaries()
    if code != 0:
        return code
    report_path = report_path if report_path.is_absolute() else ROOT / report_path

    code = run_checked(
        [
            str(cli_path),
            str(SAMPLE_PATH.relative_to(ROOT)),
            str(report_path.relative_to(ROOT)),
        ]
    )
    if code != 0:
        return code

    code = run_checked([str(tests_path)])
    if code != 0:
        return code

    print()
    print("Shell stiffness verification completed.")
    print(f"Report: {report_path.relative_to(ROOT)}")
    return 0

"""配置驱动的单元矩阵生成和验证适配器。"""

from __future__ import annotations

import os
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from .matrix_validation import compare_matrices, read_square_matrix, validate_reference_matrix
from .project_config import DEFAULT_PROJECT_PATH, ProjectConfig, load_project_config


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build" / "verification"
DEFAULT_REPORT = ROOT / "docs" / "verification" / "sample-001-report.md"

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


def _format_command(
    command: tuple[str, ...],
    project: ProjectConfig,
    sample_path: Path | None = None,
    report_path: Path | None = None,
) -> list[str]:
    values = {
        "root": str(ROOT),
        "project": str(project.path),
        "sample": str(sample_path) if sample_path else "",
        "report": str(report_path) if report_path else "",
    }
    return [token.format(**values) for token in command]


def prepare_adapter(project: ProjectConfig) -> tuple[int, dict[str, Any]]:
    """构建一次适配器，返回后续样本验证所需的运行信息。"""
    if project.adapter_kind == "builtin_s4":
        code, cli_path, tests_path = compile_verification_binaries()
        return code, {"cli_path": cli_path, "tests_path": tests_path}
    code = (
        run_checked(_format_command(project.build_command, project))
        if project.build_command
        else 0
    )
    return code, {}


def sample_matrix_paths(meta_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    reference = payload.get("reference_matrix", payload.get("abaqus_matrix"))
    implementation = payload.get("implementation_matrix", payload.get("cpp_matrix"))
    if not isinstance(reference, str) or not isinstance(implementation, str):
        raise ValueError(
            f"样本必须提供 reference_matrix/implementation_matrix：{meta_path}"
        )
    return ROOT / reference, ROOT / implementation, payload


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _write_generic_report(
    project: ProjectConfig,
    meta_path: Path,
    report_path: Path,
) -> None:
    reference_path, implementation_path, payload = sample_matrix_paths(meta_path)
    expected = validate_reference_matrix(reference_path, project.matrix_size)
    actual = read_square_matrix(implementation_path, project.matrix_size)
    metrics = compare_matrices(actual, expected)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# 单元矩阵验证报告：{payload.get('sample_id', meta_path.stem)}",
        "",
        "## 项目信息",
        f"- project_id: {project.project_id}",
        f"- element_type: {payload.get('element_type', project.element_type)}",
        f"- matrix_dimensions: {project.matrix_size} x {project.matrix_size}",
        f"- reference matrix: {_display_path(reference_path)}",
        f"- implementation matrix: {_display_path(implementation_path)}",
        "",
        "## 误差指标",
        f"- Frobenius relative error: {metrics['frobenius_relative_error']}",
        f"- max absolute error: {metrics['max_absolute_error']}",
        f"- max relative entry error: {metrics['max_relative_entry_error']}",
        f"- symmetry error: {metrics['symmetry_error']}",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def evaluate_sample(
    project: ProjectConfig,
    runtime: dict[str, Any],
    sample_path: Path,
    report_path: Path,
) -> int:
    sample_path = sample_path if sample_path.is_absolute() else ROOT / sample_path
    report_path = report_path if report_path.is_absolute() else ROOT / report_path
    if project.adapter_kind == "builtin_s4":
        return run_checked(
            [
                str(runtime["cli_path"]),
                str(sample_path.relative_to(ROOT)),
                str(report_path.relative_to(ROOT)),
            ]
        )
    code = run_checked(
        _format_command(project.evaluate_command, project, sample_path, report_path)
    )
    if code != 0:
        return code
    try:
        _write_generic_report(project, sample_path, report_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Generic matrix validation failed: {exc}", file=sys.stderr)
        return 4
    return 0


def run_adapter_tests(project: ProjectConfig, runtime: dict[str, Any]) -> int:
    if project.adapter_kind == "builtin_s4":
        return run_checked([str(runtime["tests_path"])])
    if not project.test_command:
        return 0
    return run_checked(_format_command(project.test_command, project))


def run_verification(
    report_path: Path = DEFAULT_REPORT,
    project_path: Path = DEFAULT_PROJECT_PATH,
    sample_path: Path | None = None,
) -> int:
    """构建当前适配器，验证主样本并运行适配器测试。"""
    try:
        project = load_project_config(project_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Project configuration error: {exc}", file=sys.stderr)
        return 4
    code, runtime = prepare_adapter(project)
    if code != 0:
        return code
    report_path = report_path if report_path.is_absolute() else ROOT / report_path
    selected_sample = sample_path or project.primary_sample_path

    code = evaluate_sample(project, runtime, selected_sample, report_path)
    if code != 0:
        return code

    code = run_adapter_tests(project, runtime)
    if code != 0:
        return code

    print()
    print("Element matrix verification completed.")
    print(f"Report: {report_path.relative_to(ROOT)}")
    return 0

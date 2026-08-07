#!/usr/bin/env python3
"""正式多智能体数值迭代闭环。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_openai_client import call_openai_agent, load_openai_config


ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT / "agents" / "prompts"
RUNS_DIR = ROOT / "workflow" / "runs"
SOURCE_PATH = ROOT / "src" / "shell" / "ShellStiffness.cpp"
REPORT_PATH = ROOT / "docs" / "verification" / "sample-001-report.md"
ABAQUS_MATRIX_PATH = ROOT / "data" / "abaqus" / "matrix" / "sample_001_abaqus_s4.csv"
CPP_MATRIX_PATH = ROOT / "data" / "cpp" / "sample_001_cpp.csv"
PROGRESS_OVERVIEW_PATH = ROOT / "docs" / "PROJECT_PROGRESS.md"
PROGRESS_LOG_PATH = ROOT / "docs" / "verification" / "progress-log.md"
LATEST_REPORT_PATH = ROOT / "docs" / "verification" / "agent-latest.md"
EXPERIMENT_MEMORY_PATH = ROOT / "workflow" / "experiment-memory.json"

ALLOWED_PATCH_PATHS = {"src/shell/ShellStiffness.cpp"}
GLOBAL_METRIC_KEYS = {
    "frobenius_relative_error",
    "max_absolute_error",
    "max_relative_entry_error",
    "symmetry_error",
}
BLOCK_NAMES = {"membrane_xy", "bending_shear", "drilling"}
BLOCK_METRIC_KEYS = {
    f"{row_name}__{col_name}"
    for row_name in BLOCK_NAMES
    for col_name in BLOCK_NAMES
}
ALLOWED_EXPECTED_METRICS = GLOBAL_METRIC_KEYS | BLOCK_METRIC_KEYS
MIN_FROBENIUS_ABSOLUTE_DROP = 1.0e-6
MIN_FROBENIUS_RELATIVE_DROP = 1.0e-4
MAX_SYMMETRY_ERROR = 1.0e-12
MAX_ABSOLUTE_ERROR_REGRESSION = 0.01
MAX_NON_TARGET_BLOCK_REGRESSION = 0.05
BANNED_ADDED_TOKENS = {
    "system(",
    "popen(",
    "std::filesystem",
    "<filesystem>",
    "<fstream>",
    "<unistd.h>",
    "<curl/",
    "OPENAI_API_KEY",
    "std::remove(",
}
STATUS_START = "<!-- AGENT_WORKFLOW_STATUS_START -->"
STATUS_END = "<!-- AGENT_WORKFLOW_STATUS_END -->"


def console(message: str = "") -> None:
    print(message, flush=True)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise RuntimeError(f"缺少 Agent 提示词：{path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8").strip()


def render_prompt(filename: str, context: str) -> str:
    template = load_prompt(filename)
    marker = "{{CONTEXT}}"
    if marker not in template:
        raise RuntimeError(f"提示词缺少 {marker}：{filename}")
    return template.replace(marker, context)


def read_limited(path: Path, max_chars: int = 30000) -> str:
    if not path.exists():
        return f"[文件不存在：{path.relative_to(ROOT)}]"
    content = path.read_text(encoding="utf-8", errors="replace")
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + f"\n\n[已截断 {len(content) - max_chars} 个字符]"


def compact_text(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n[已截断 {len(text) - max_chars} 个字符]"


def patch_fingerprint(diff: str) -> str:
    """仅按实际增删代码生成指纹，忽略上下文、行号和注释差异。"""
    semantic_lines: list[str] = []
    for line in diff.splitlines():
        if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        content = line[1:].strip()
        if not content or content.startswith("//"):
            continue
        content = re.sub(r"\s*//.*$", "", content).strip()
        if content:
            semantic_lines.append(f"{line[0]}{content}")
    if not semantic_lines:
        return ""
    normalized = "\n".join(semantic_lines)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_duplicate_patch(
    diff: str,
    experiment_memory: dict[str, Any],
    attempted_fingerprints: list[str] | None = None,
) -> tuple[str, list[str]]:
    """返回候选补丁指纹及命中的历史实验或当前运行尝试。"""
    fingerprint = patch_fingerprint(diff)
    if not fingerprint:
        return "", ["semantic-empty-patch"]

    matches: list[str] = []
    if fingerprint in (attempted_fingerprints or []):
        matches.append("current-run-attempt")

    for item in experiment_memory.get("experiments", []):
        if not isinstance(item, dict):
            continue
        historical = str(item.get("patch_fingerprint", ""))
        if not historical:
            historical = patch_fingerprint(str(item.get("patch_excerpt", "")))
        if historical == fingerprint:
            matches.append(str(item.get("id", "historical-experiment")))
    return fingerprint, matches


def experiment_id(run_id: str, iteration_number: int) -> str:
    return f"{run_id}:iteration-{iteration_number:02d}"


def build_experiment_record(
    run_id: str, iteration: dict[str, Any], iteration_dir: Path
) -> dict[str, Any]:
    """把单轮事实压缩成可跨运行复用的实验记忆。"""
    record_id = experiment_id(run_id, int(iteration["iteration"]))
    do_not_repeat = iteration.get("do_not_repeat", [])
    if isinstance(do_not_repeat, str):
        do_not_repeat = [do_not_repeat] if do_not_repeat.strip() else []
    if not isinstance(do_not_repeat, list):
        do_not_repeat = []
    accepted = bool(iteration.get("accepted", False))
    if not accepted and not do_not_repeat:
        do_not_repeat = [f"不得原样重复实验 {record_id} 的理论假设和补丁机制"]
    reviewer_summary = str(iteration.get("reviewer_summary", ""))
    failure_mechanism = str(
        iteration.get("failure_mechanism")
        or iteration.get("failure")
        or reviewer_summary
    )
    patch_text = read_limited(iteration_dir / "developer.patch", 2600)
    return {
        "id": record_id,
        "run_id": run_id,
        "iteration": int(iteration["iteration"]),
        "before_error": iteration.get("before_error"),
        "candidate_error": iteration.get("candidate_error"),
        "patch_applied": bool(iteration.get("patch_applied", False)),
        "test_passed": bool(iteration.get("test_passed", False)),
        "accepted": accepted,
        "reviewer_decision": iteration.get("reviewer_decision", "reject"),
        "reviewer_summary": compact_text(reviewer_summary, 1600),
        "failure_mechanism": compact_text(failure_mechanism, 1000),
        "do_not_repeat": [compact_text(str(item), 500) for item in do_not_repeat],
        "next_focus": compact_text(str(iteration.get("next_focus", "")), 1000),
        "experiment_plan": iteration.get("experiment_plan", {}),
        "candidate_block_relative_errors": (
            iteration.get("candidate_diagnostics", {}).get("block_relative_errors", {})
            if isinstance(iteration.get("candidate_diagnostics"), dict)
            else {}
        ),
        "patch_fingerprint": str(
            iteration.get("patch_fingerprint") or patch_fingerprint(patch_text)
        ),
        "theory_excerpt": compact_text(read_limited(iteration_dir / "theory-analysis.md"), 2200),
        "patch_excerpt": compact_text(patch_text, 2600),
    }


def load_experiment_memory(path: Path = EXPERIMENT_MEMORY_PATH) -> dict[str, Any]:
    """读取持久化记忆，并自动补录尚未进入记忆文件的历史 run。"""
    memory: dict[str, Any] = {"schema_version": 1, "experiments": []}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("experiments"), list):
                memory = loaded
        except (json.JSONDecodeError, OSError):
            pass

    for item in memory["experiments"]:
        if not isinstance(item, dict) or item.get("accepted", False):
            continue
        if not item.get("failure_mechanism"):
            item["failure_mechanism"] = item.get("reviewer_summary", "")
        if not item.get("do_not_repeat"):
            item["do_not_repeat"] = [
                f"不得原样重复实验 {item.get('id', 'unknown')} 的理论假设和补丁机制"
            ]

    known_ids = {
        str(item.get("id"))
        for item in memory["experiments"]
        if isinstance(item, dict) and item.get("id")
    }
    state_paths = {
        *RUNS_DIR.glob("stage3-*/state.json"),
        *RUNS_DIR.glob("run-*/state.json"),
    }
    for state_path in sorted(state_paths):
        try:
            historical_state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        run_id = str(historical_state.get("run_id", state_path.parent.name))
        for iteration in historical_state.get("iterations", []):
            if not isinstance(iteration, dict) or "iteration" not in iteration:
                continue
            record_id = experiment_id(run_id, int(iteration["iteration"]))
            if record_id in known_ids:
                continue
            iteration_dir = state_path.parent / f"iteration-{int(iteration['iteration']):02d}"
            memory["experiments"].append(build_experiment_record(run_id, iteration, iteration_dir))
            known_ids.add(record_id)
    memory["experiments"] = memory["experiments"][-100:]
    return memory


def save_experiment_record(
    memory: dict[str, Any], record: dict[str, Any], path: Path = EXPERIMENT_MEMORY_PATH
) -> None:
    experiments = [
        item for item in memory.get("experiments", []) if item.get("id") != record["id"]
    ]
    experiments.append(record)
    memory["schema_version"] = 1
    memory["experiments"] = experiments[-100:]
    write_json(path, memory)


def render_experiment_memory(
    memory: dict[str, Any],
    limit: int = 10,
    max_chars: int = 30000,
) -> str:
    experiments = memory.get("experiments", [])
    if not experiments:
        return "无历史实验。"
    return compact_text(
        json.dumps(experiments[-limit:], ensure_ascii=False, indent=2),
        max_chars,
    )


def agent_state_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    """生成面向 LLM 的精简状态，避免重复传输长期记忆和完整诊断。"""
    scalar_keys = (
        "run_id",
        "runtime",
        "target_error",
        "max_iterations",
        "initial_error",
        "current_error",
        "accepted_iterations",
        "status",
        "iteration_number",
        "planning_attempt",
    )
    snapshot = {key: state[key] for key in scalar_keys if key in state}
    verification = state.get("current_verification", {})
    if isinstance(verification, dict):
        snapshot["current_metrics"] = verification.get("metrics", {})

    iteration = state.get("iteration", {})
    if isinstance(iteration, dict) and iteration:
        snapshot["current_iteration"] = {
            key: iteration[key]
            for key in (
                "iteration",
                "before_error",
                "planning_attempt",
                "patch_fingerprint",
                "duplicate_patch",
                "duplicate_matches",
                "failure",
            )
            if key in iteration
        }
    attempted = state.get("attempted_patch_fingerprints", [])
    if isinstance(attempted, list):
        snapshot["attempted_patch_fingerprints"] = attempted[-10:]
    return snapshot


def run_command(command: list[str], log_path: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    write_text(
        log_path,
        "\n".join(
            [
                f"$ {' '.join(command)}",
                f"exit_code={result.returncode}",
                "",
                "## stdout",
                result.stdout,
                "## stderr",
                result.stderr,
            ]
        ),
    )
    return result


def parse_verification_report(path: Path = REPORT_PATH) -> dict[str, float]:
    text = path.read_text(encoding="utf-8")
    labels = {
        "frobenius_relative_error": "Frobenius relative error",
        "max_absolute_error": "max absolute error",
        "max_relative_entry_error": "max relative entry error",
        "symmetry_error": "symmetry error",
    }
    metrics: dict[str, float] = {}
    for key, label in labels.items():
        match = re.search(rf"{re.escape(label)}:\s*([-+0-9.eE]+)", text)
        if not match:
            raise RuntimeError(f"验证报告缺少指标：{label}")
        metrics[key] = float(match.group(1))
    return metrics


def read_matrix(path: Path) -> list[list[float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        matrix = [[float(cell) for cell in row] for row in csv.reader(handle) if row]
    if len(matrix) != 24 or any(len(row) != 24 for row in matrix):
        raise RuntimeError(f"矩阵不是 24 x 24：{path.relative_to(ROOT)}")
    return matrix


def relative_block_error(actual: list[list[float]], expected: list[list[float]], rows: list[int], cols: list[int]) -> float:
    difference = 0.0
    reference = 0.0
    for row in rows:
        for col in cols:
            delta = actual[row][col] - expected[row][col]
            difference += delta * delta
            reference += expected[row][col] * expected[row][col]
    return math.sqrt(difference) / math.sqrt(reference) if reference > 0.0 else math.sqrt(difference)


def dof_label(index: int) -> str:
    names = ["ux", "uy", "uz", "rx", "ry", "rz"]
    return f"n{index // 6 + 1}.{names[index % 6]}"


def matrix_diagnostics(actual_path: Path = CPP_MATRIX_PATH, expected_path: Path = ABAQUS_MATRIX_PATH) -> dict[str, Any]:
    actual = read_matrix(actual_path)
    expected = read_matrix(expected_path)
    groups = {
        "membrane_xy": [node * 6 + dof for node in range(4) for dof in (0, 1)],
        "bending_shear": [node * 6 + dof for node in range(4) for dof in (2, 3, 4)],
        "drilling": [node * 6 + 5 for node in range(4)],
    }
    block_errors: dict[str, float] = {}
    for row_name, rows in groups.items():
        for col_name, cols in groups.items():
            block_errors[f"{row_name}__{col_name}"] = relative_block_error(actual, expected, rows, cols)

    entries: list[dict[str, Any]] = []
    for row in range(24):
        for col in range(24):
            difference = actual[row][col] - expected[row][col]
            entries.append(
                {
                    "row": dof_label(row),
                    "col": dof_label(col),
                    "actual": actual[row][col],
                    "expected": expected[row][col],
                    "difference": difference,
                    "absolute_difference": abs(difference),
                }
            )
    entries.sort(key=lambda item: item["absolute_difference"], reverse=True)
    return {"block_relative_errors": block_errors, "largest_absolute_entries": entries[:20]}


def compare_expected_metrics(
    expected_metrics: list[str],
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, dict[str, float | bool]]:
    """按规划智能体声明的稳定指标键生成候选前后对比。"""
    baseline_values = {
        **baseline.get("metrics", {}),
        **baseline.get("diagnostics", {}).get("block_relative_errors", {}),
    }
    candidate_values = {
        **candidate.get("metrics", {}),
        **candidate.get("diagnostics", {}).get("block_relative_errors", {}),
    }
    missing = [
        key
        for key in expected_metrics
        if key not in baseline_values or key not in candidate_values
    ]
    if missing:
        raise ValueError(f"预期指标缺少实际数值：{missing}")

    comparison: dict[str, dict[str, float | bool]] = {}
    for key in expected_metrics:
        before = float(baseline_values[key])
        after = float(candidate_values[key])
        comparison[key] = {
            "before": before,
            "after": after,
            "delta": after - before,
            "improved": after < before,
        }
    return comparison


def evaluate_candidate_gate(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    primary_metric: str,
    test_passed: bool,
) -> dict[str, Any]:
    """执行不受智能体控制的本地数值接受门槛。"""
    before_metrics = baseline.get("metrics", {})
    after_metrics = candidate.get("metrics", {})
    before_blocks = baseline.get("diagnostics", {}).get("block_relative_errors", {})
    after_blocks = candidate.get("diagnostics", {}).get("block_relative_errors", {})

    required_global = {
        "frobenius_relative_error",
        "max_absolute_error",
        "symmetry_error",
    }
    missing_global = sorted(
        key
        for key in required_global
        if key not in before_metrics or key not in after_metrics
    )
    missing_blocks = sorted(
        key for key in BLOCK_METRIC_KEYS if key not in before_blocks or key not in after_blocks
    )
    if missing_global or missing_blocks or primary_metric not in BLOCK_METRIC_KEYS:
        return {
            "passed": False,
            "test_passed": bool(test_passed),
            "reason": "missing-or-invalid-metrics",
            "missing_global_metrics": missing_global,
            "missing_block_metrics": missing_blocks,
            "primary_metric": primary_metric,
        }

    before_frobenius = float(before_metrics["frobenius_relative_error"])
    after_frobenius = float(after_metrics["frobenius_relative_error"])
    absolute_drop = before_frobenius - after_frobenius
    relative_drop = absolute_drop / before_frobenius if before_frobenius > 0.0 else 0.0
    frobenius_improved = (
        absolute_drop >= MIN_FROBENIUS_ABSOLUTE_DROP
        and relative_drop >= MIN_FROBENIUS_RELATIVE_DROP
    )

    primary_before = float(before_blocks[primary_metric])
    primary_after = float(after_blocks[primary_metric])
    primary_improved = primary_after < primary_before

    symmetry_after = float(after_metrics["symmetry_error"])
    symmetry_passed = symmetry_after < MAX_SYMMETRY_ERROR

    max_absolute_before = float(before_metrics["max_absolute_error"])
    max_absolute_after = float(after_metrics["max_absolute_error"])
    max_absolute_limit = max_absolute_before * (1.0 + MAX_ABSOLUTE_ERROR_REGRESSION)
    max_absolute_passed = max_absolute_after <= max_absolute_limit

    block_regressions: dict[str, dict[str, float]] = {}
    for key in sorted(BLOCK_METRIC_KEYS - {primary_metric}):
        before = float(before_blocks[key])
        after = float(after_blocks[key])
        limit = before * (1.0 + MAX_NON_TARGET_BLOCK_REGRESSION)
        if (before > 1.0e-12 and after > limit) or (
            before <= 1.0e-12 and after > 1.0e-12
        ):
            block_regressions[key] = {
                "before": before,
                "after": after,
                "limit": limit if before > 1.0e-12 else 1.0e-12,
            }

    passed = bool(
        test_passed
        and frobenius_improved
        and primary_improved
        and symmetry_passed
        and max_absolute_passed
        and not block_regressions
    )
    return {
        "passed": passed,
        "test_passed": bool(test_passed),
        "primary_metric": primary_metric,
        "frobenius": {
            "before": before_frobenius,
            "after": after_frobenius,
            "absolute_drop": absolute_drop,
            "relative_drop": relative_drop,
            "passed": frobenius_improved,
        },
        "primary": {
            "before": primary_before,
            "after": primary_after,
            "passed": primary_improved,
        },
        "symmetry": {
            "after": symmetry_after,
            "limit": MAX_SYMMETRY_ERROR,
            "passed": symmetry_passed,
        },
        "max_absolute_error": {
            "before": max_absolute_before,
            "after": max_absolute_after,
            "limit": max_absolute_limit,
            "passed": max_absolute_passed,
        },
        "non_target_block_regressions": block_regressions,
    }


def run_verification(iteration_dir: Path, label: str) -> dict[str, Any]:
    log_path = iteration_dir / f"verification-{label}.log"
    report_mtime = REPORT_PATH.stat().st_mtime_ns if REPORT_PATH.exists() else None
    result = run_command(
        [
            sys.executable,
            "-m",
            "shell_agent",
            "verify",
            "--report",
            str(REPORT_PATH.relative_to(ROOT)),
        ],
        log_path,
    )
    outcome: dict[str, Any] = {"exit_code": result.returncode, "log": str(log_path.relative_to(ROOT))}
    report_updated = (
        REPORT_PATH.exists()
        and (report_mtime is None or REPORT_PATH.stat().st_mtime_ns != report_mtime)
    )
    if report_updated:
        outcome["metrics"] = parse_verification_report()
        outcome["diagnostics"] = matrix_diagnostics()
    return outcome


def extract_unified_diff(text: str) -> str:
    match = re.search(r"BEGIN_UNIFIED_DIFF\s*(.*?)\s*END_UNIFIED_DIFF", text, flags=re.DOTALL)
    if not match:
        raise ValueError("Developer Agent 输出中缺少 BEGIN_UNIFIED_DIFF/END_UNIFIED_DIFF")
    diff = match.group(1).strip()
    if diff.startswith("```diff"):
        diff = diff[len("```diff") :].lstrip("\n")
    elif diff.startswith("```"):
        diff = diff[3:].lstrip("\n")
    if diff.endswith("```"):
        diff = diff[:-3].rstrip()
    return diff + "\n"


def normalize_patch_path(raw_path: str) -> str:
    path = raw_path.split("\t", 1)[0].split(" ", 1)[0].strip()
    if path.startswith("a/") or path.startswith("b/"):
        path = path[2:]
    return path


def validate_unified_diff(diff: str) -> list[str]:
    if len(diff) > 120000 or diff.count("\n") > 1400:
        raise ValueError("补丁超过单轮大小限制")
    if "@@" not in diff:
        raise ValueError("补丁缺少 unified diff hunk")

    paths: list[str] = []
    for line in diff.splitlines():
        if line.startswith("--- ") or line.startswith("+++ "):
            path = normalize_patch_path(line[4:])
            if path == "/dev/null":
                raise ValueError("工作流不允许新增或删除文件")
            paths.append(path)
        if line.startswith("+") and not line.startswith("+++"):
            for token in BANNED_ADDED_TOKENS:
                if token in line:
                    raise ValueError(f"补丁包含禁止调用：{token}")

    if not paths or any(path not in ALLOWED_PATCH_PATHS for path in paths):
        raise ValueError(f"Developer Agent 只能修改：{sorted(ALLOWED_PATCH_PATHS)}；实际路径：{paths}")
    return sorted(set(paths))


def apply_unified_diff(diff: str, iteration_dir: Path) -> dict[str, Any]:
    patch_path = iteration_dir / "developer.patch"
    write_text(patch_path, diff)
    dry_run = run_command(
        ["git", "apply", "--check", "--recount", str(patch_path)],
        iteration_dir / "patch-dry-run.log",
    )
    if dry_run.returncode != 0:
        return {"applied": False, "reason": "patch dry-run failed"}
    applied = run_command(
        ["git", "apply", "--recount", str(patch_path)],
        iteration_dir / "patch-apply.log",
    )
    return {"applied": applied.returncode == 0, "reason": "applied" if applied.returncode == 0 else "patch apply failed"}


def extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Agent 没有返回 JSON 对象")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Agent 返回值不是 JSON 对象")
    return payload


def validate_experiment_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """校验规划智能体的结构化输出，避免下游依赖模糊文本。"""
    required_strings = {
        "hypothesis_id",
        "experiment_class",
        "target_block",
        "mechanism",
        "difference_from_history",
        "primary_metric",
    }
    missing = [
        key for key in required_strings
        if not isinstance(plan.get(key), str) or not str(plan[key]).strip()
    ]
    if missing:
        raise ValueError(f"Experiment Planner 缺少字段：{missing}")

    allowed_classes = {
        "membrane",
        "bending",
        "transverse_shear",
        "drilling",
        "dof_mapping",
        "local_coordinates",
        "integration",
    }
    if plan["experiment_class"] not in allowed_classes:
        raise ValueError(
            "Experiment Planner 的 experiment_class 无效："
            f"{plan['experiment_class']}"
        )

    for key in ("allowed_changes", "forbidden_changes", "expected_metrics"):
        value = plan.get(key)
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            raise ValueError(f"Experiment Planner 字段 {key} 必须是非空字符串数组")
    expected_metrics = plan["expected_metrics"]
    if "frobenius_relative_error" not in expected_metrics:
        raise ValueError("Experiment Planner 的 expected_metrics 必须包含 frobenius_relative_error")
    invalid_metrics = sorted(set(expected_metrics) - ALLOWED_EXPECTED_METRICS)
    if invalid_metrics:
        raise ValueError(
            "Experiment Planner 使用了未知 expected_metrics："
            f"{invalid_metrics}；允许值：{sorted(ALLOWED_EXPECTED_METRICS)}"
        )
    if plan["primary_metric"] not in BLOCK_METRIC_KEYS:
        raise ValueError(
            "Experiment Planner 的 primary_metric 必须是合法分块指标："
            f"{plan['primary_metric']}"
        )
    if plan["primary_metric"] not in expected_metrics:
        raise ValueError("Experiment Planner 的 primary_metric 必须包含在 expected_metrics 中")
    return plan


def experiment_planner_agent(
    state: dict[str, Any],
    iteration_dir: Path,
    previous_feedback: str,
    experiment_memory: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """选择本轮唯一实验类别，并明确允许和禁止的修改范围。"""
    context = "\n\n".join(
        [
            "# 当前状态",
            json.dumps(agent_state_snapshot(state), ensure_ascii=False, indent=2),
            "# 当前矩阵诊断",
            json.dumps(
                state["current_verification"].get("diagnostics", {}),
                ensure_ascii=False,
                indent=2,
            ),
            "# 上一轮 Reviewer 或本地闸门反馈",
            previous_feedback or "无，这是第一轮。",
            "# 跨运行历史实验记忆",
            render_experiment_memory(experiment_memory, limit=6, max_chars=12000),
        ]
    )
    output = call_openai_agent(
        load_prompt("workflow/planner.system.md"),
        render_prompt("workflow/planner.user.md", context),
    )
    write_text(iteration_dir / "experiment-planner-response.md", output + "\n")
    plan = validate_experiment_plan(extract_json_object(output))
    write_json(iteration_dir / "experiment-plan.json", plan)
    return plan, output


def theory_agent(
    state: dict[str, Any],
    iteration_dir: Path,
    previous_feedback: str,
    experiment_memory: dict[str, Any],
    experiment_plan: dict[str, Any] | None = None,
) -> str:
    context = "\n\n".join(
        [
            "# 当前状态",
            json.dumps(agent_state_snapshot(state), ensure_ascii=False, indent=2),
            "# 当前矩阵诊断",
            json.dumps(state["current_verification"].get("diagnostics", {}), ensure_ascii=False, indent=2),
            "# Experiment Planner 本轮计划",
            json.dumps(experiment_plan or {}, ensure_ascii=False, indent=2),
            "# 上一轮 Reviewer 反馈",
            previous_feedback or "无，这是第一轮。",
            "# 当前 ShellStiffness.cpp",
            read_limited(SOURCE_PATH, 9000),
            "# 历史实验说明",
            "Experiment Planner 已检查跨运行历史并把结论写入 difference_from_history 与 forbidden_changes。",
        ]
    )
    output = call_openai_agent(load_prompt("workflow/theory.system.md"), render_prompt("workflow/theory.user.md", context))
    write_text(iteration_dir / "theory-analysis.md", output + "\n")
    return output


def developer_agent(
    state: dict[str, Any],
    theory_output: str,
    iteration_dir: Path,
    previous_feedback: str,
    experiment_memory: dict[str, Any],
    correction: str = "",
    experiment_plan: dict[str, Any] | None = None,
) -> str:
    context = "\n\n".join(
        [
            "# 当前状态",
            json.dumps(agent_state_snapshot(state), ensure_ascii=False, indent=2),
            "# Theory Agent 诊断",
            theory_output,
            "# Experiment Planner 本轮计划",
            json.dumps(experiment_plan or {}, ensure_ascii=False, indent=2),
            "# Reviewer 上轮反馈",
            previous_feedback or "无",
            "# 跨运行历史实验记忆",
            render_experiment_memory(experiment_memory, limit=2, max_chars=3000),
            "# 输出协议纠正",
            correction or "首次生成：严格按提示词输出完整 unified diff。",
            "# 允许修改的当前文件",
            read_limited(SOURCE_PATH, 50000),
            "# 当前测试约束",
            read_limited(ROOT / "tests" / "shell_stiffness_tests.cpp", 5000),
        ]
    )
    output = call_openai_agent(load_prompt("workflow/developer.system.md"), render_prompt("workflow/developer.user.md", context))
    write_text(iteration_dir / "developer-response.md", output + "\n")
    return output


def developer_patch_with_retry(
    state: dict[str, Any],
    theory_output: str,
    iteration_dir: Path,
    previous_feedback: str,
    experiment_memory: dict[str, Any],
    experiment_plan: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """最多请求两次；第二次仅纠正补丁协议，不改变理论方向。"""
    correction = ""
    last_error: Exception | None = None
    for attempt in range(1, 3):
        output = developer_agent(
            state,
            theory_output,
            iteration_dir,
            previous_feedback,
            experiment_memory,
            correction,
            experiment_plan,
        )
        write_text(iteration_dir / f"developer-response-{attempt}.md", output + "\n")
        try:
            diff = extract_unified_diff(output)
            paths = validate_unified_diff(diff)
            return diff, paths
        except Exception as exc:
            last_error = exc
            correction = (
                f"上一次输出不能使用：{exc}。请重新输出完整补丁；必须同时包含 "
                "BEGIN_UNIFIED_DIFF 和 END_UNIFIED_DIFF，必须包含真实的加减修改行，"
                "不得输出 *** Begin Patch 或 *** End Patch，也不要在标记外输出文字。"
            )
    raise ValueError(f"Developer Agent 连续两次未返回有效补丁：{last_error}")


def reviewer_agent(
    state: dict[str, Any],
    iteration: dict[str, Any],
    iteration_dir: Path,
    experiment_memory: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    context = "\n\n".join(
        [
            "# 迭代前状态",
            json.dumps(agent_state_snapshot(state), ensure_ascii=False, indent=2),
            "# 候选前矩阵诊断",
            json.dumps(
                state.get("current_verification", {}).get("diagnostics", {}),
                ensure_ascii=False,
                indent=2,
            ),
            "# 本轮事实",
            json.dumps(iteration, ensure_ascii=False, indent=2),
            "# 跨运行历史实验记忆",
            render_experiment_memory(experiment_memory, limit=2, max_chars=3000),
            "# Theory Agent 输出",
            read_limited(iteration_dir / "theory-analysis.md"),
            "# Developer Agent 输出",
            read_limited(iteration_dir / "developer-response.md"),
            "# 测试日志",
            read_limited(iteration_dir / "verification-candidate.log", 5000),
        ]
    )
    output = call_openai_agent(load_prompt("workflow/reviewer.system.md"), render_prompt("workflow/reviewer.user.md", context))
    write_text(iteration_dir / "reviewer-response.md", output + "\n")
    return extract_json_object(output), output


def restore_source(backup_path: Path, iteration_dir: Path) -> dict[str, Any]:
    shutil.copy2(backup_path, SOURCE_PATH)
    return run_verification(iteration_dir, "restored")


def make_summary(state: dict[str, Any]) -> str:
    lines = [
        "# 多 Agent 迭代报告",
        "",
        f"- Run ID: `{state['run_id']}`",
        f"- Runtime: `{state['runtime']}`",
        f"- Target error: `{state['target_error']}`",
        f"- Initial error: `{state['initial_error']}`",
        f"- Current error: `{state['current_error']}`",
        f"- Accepted iterations: `{state['accepted_iterations']}`",
        f"- Status: `{state['status']}`",
        "",
        "## 迭代记录",
        "",
    ]
    for item in state["iterations"]:
        lines.extend(
            [
                f"### Iteration {item['iteration']}",
                "",
                f"- Patch applied: `{item.get('patch_applied', False)}`",
                f"- Test passed: `{item.get('test_passed', False)}`",
                f"- Before error: `{item.get('before_error')}`",
                f"- Candidate error: `{item.get('candidate_error')}`",
                f"- Reviewer decision: `{item.get('reviewer_decision', 'not-called')}`",
                f"- Accepted: `{item.get('accepted', False)}`",
                f"- Summary: {item.get('reviewer_summary', item.get('failure', ''))}",
                f"- Failure mechanism: {item.get('failure_mechanism', '')}",
                f"- Do not repeat: {item.get('do_not_repeat', [])}",
                f"- Next focus: {item.get('next_focus', '')}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def update_progress_overview_status(
    state: dict[str, Any], progress_path: Path = PROGRESS_OVERVIEW_PATH
) -> None:
    if not progress_path.exists():
        return
    text = progress_path.read_text(encoding="utf-8")
    if STATUS_START not in text or STATUS_END not in text:
        return
    block = "\n".join(
        [
            STATUS_START,
            "### Agent 自动迭代状态",
            "",
            f"- 最近运行：`{state['run_id']}`",
            f"- 状态：`{state['status']}`",
            f"- 初始误差：`{state['initial_error']}`",
            f"- 当前误差：`{state['current_error']}`",
            f"- 目标误差：`{state['target_error']}`",
            f"- 已接受迭代：`{state['accepted_iterations']}`",
            f"- 运行报告：`workflow/runs/{state['run_id']}/summary.md`",
            STATUS_END,
        ]
    )
    pattern = re.compile(
        re.escape(STATUS_START) + r".*?" + re.escape(STATUS_END),
        flags=re.DOTALL,
    )
    progress_path.write_text(pattern.sub(block, text), encoding="utf-8")


def append_progress_log(state: dict[str, Any], progress_path: Path = PROGRESS_LOG_PATH) -> None:
    if not progress_path.exists():
        return
    text = progress_path.read_text(encoding="utf-8")
    if state["run_id"] in text:
        return
    entry = "\n".join(
        [
            "",
            f"## {datetime.now().date().isoformat()}：多 Agent 自动迭代 `{state['run_id']}`",
            "",
            f"- 状态：`{state['status']}`",
            f"- 初始误差：`{state['initial_error']}`",
            f"- 当前误差：`{state['current_error']}`",
            f"- 已接受迭代：`{state['accepted_iterations']}`",
            f"- 报告：`workflow/runs/{state['run_id']}/summary.md`",
            "",
        ]
    )
    progress_path.write_text(text.rstrip() + "\n" + entry, encoding="utf-8")


def progress_agent(state: dict[str, Any], run_dir: Path) -> None:
    summary = make_summary(state)
    write_text(run_dir / "summary.md", summary)
    write_text(LATEST_REPORT_PATH, summary)
    update_progress_overview_status(state)
    append_progress_log(state)


def run_workflow(max_iterations: int, target_error: float) -> int:
    cfg = load_openai_config()
    run_id = datetime.now().strftime("run-%Y%m%d-%H%M%S")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    experiment_memory = load_experiment_memory()
    write_json(EXPERIMENT_MEMORY_PATH, experiment_memory)

    console(f"在线多 Agent 迭代：{run_id}")
    console("[1] Coordinator Agent：初始化并运行基线验证")
    baseline = run_verification(run_dir, "baseline")
    if baseline["exit_code"] != 0:
        raise RuntimeError(f"基线验证失败，见 {baseline['log']}")

    initial_error = baseline["metrics"]["frobenius_relative_error"]
    state: dict[str, Any] = {
        "run_id": run_id,
        "runtime": f"openai:{cfg.model}",
        "target_error": target_error,
        "max_iterations": max_iterations,
        "initial_error": initial_error,
        "current_error": initial_error,
        "accepted_iterations": 0,
        "status": "running",
        "current_verification": baseline,
        "experiment_memory": {
            "path": str(EXPERIMENT_MEMORY_PATH.relative_to(ROOT)),
            "loaded_experiments": len(experiment_memory["experiments"]),
        },
        "iterations": [],
    }
    write_json(run_dir / "state.json", state)

    previous_feedback = ""
    for iteration_number in range(1, max_iterations + 1):
        if state["current_error"] <= target_error:
            state["status"] = "target_reached"
            break

        iteration_dir = run_dir / f"iteration-{iteration_number:02d}"
        iteration_dir.mkdir(parents=True, exist_ok=False)
        backup_path = iteration_dir / "ShellStiffness.cpp.before"
        shutil.copy2(SOURCE_PATH, backup_path)
        iteration: dict[str, Any] = {"iteration": iteration_number, "before_error": state["current_error"]}

        console(f"[{iteration_number}/{max_iterations}] Theory Research Agent：诊断矩阵误差")
        try:
            theory_output = theory_agent(
                state, iteration_dir, previous_feedback, experiment_memory
            )
            console(f"[{iteration_number}/{max_iterations}] Developer Agent：生成受限 unified diff")
            diff, patch_paths = developer_patch_with_retry(
                state,
                theory_output,
                iteration_dir,
                previous_feedback,
                experiment_memory,
            )
            iteration["patch_paths"] = patch_paths
            apply_result = apply_unified_diff(diff, iteration_dir)
            iteration["patch_applied"] = apply_result["applied"]
            if not apply_result["applied"]:
                iteration["failure"] = apply_result["reason"]
        except Exception as exc:
            iteration["patch_applied"] = False
            iteration["failure"] = str(exc)

        candidate: dict[str, Any] = {"exit_code": -1}
        if iteration["patch_applied"]:
            console(f"[{iteration_number}/{max_iterations}] Test Agent：编译、Catch2、Abaqus 误差比较")
            candidate = run_verification(iteration_dir, "candidate")
        iteration["test_passed"] = candidate.get("exit_code") == 0
        if "metrics" in candidate:
            iteration["candidate_error"] = candidate["metrics"]["frobenius_relative_error"]
            iteration["candidate_metrics"] = candidate["metrics"]
        else:
            iteration["candidate_error"] = None

        console(f"[{iteration_number}/{max_iterations}] Reviewer Agent：在线评审接受或回退")
        try:
            review, raw_review = reviewer_agent(
                state, iteration, iteration_dir, experiment_memory
            )
            iteration["reviewer_decision"] = str(review.get("decision", "reject")).lower()
            iteration["reviewer_summary"] = str(review.get("summary", ""))
            iteration["failure_mechanism"] = str(review.get("failure_mechanism", ""))
            do_not_repeat = review.get("do_not_repeat", [])
            if isinstance(do_not_repeat, str):
                do_not_repeat = [do_not_repeat] if do_not_repeat.strip() else []
            iteration["do_not_repeat"] = do_not_repeat if isinstance(do_not_repeat, list) else []
            iteration["next_focus"] = str(review.get("next_focus", ""))
            previous_feedback = raw_review
        except Exception as exc:
            iteration["reviewer_decision"] = "reject"
            iteration["reviewer_summary"] = f"Reviewer 调用或解析失败：{exc}"
            iteration["failure_mechanism"] = "Reviewer 调用或解析失败"
            iteration["do_not_repeat"] = []
            previous_feedback = iteration["reviewer_summary"]

        improved = bool(
            iteration["test_passed"]
            and iteration["candidate_error"] is not None
            and iteration["candidate_error"] < state["current_error"] - 1.0e-9
        )
        accepted = improved and iteration["reviewer_decision"] == "accept"
        iteration["local_improvement_gate"] = improved
        iteration["accepted"] = accepted

        if accepted:
            state["current_error"] = iteration["candidate_error"]
            state["current_verification"] = candidate
            state["accepted_iterations"] += 1
            console(f"[ACCEPTED] 误差降至 {state['current_error']}")
        else:
            restore_source(backup_path, iteration_dir)
            console(f"[REJECTED] 已恢复上一版，原因：{iteration.get('reviewer_summary', iteration.get('failure', '未改善'))}")

        state["iterations"].append(iteration)
        record = build_experiment_record(run_id, iteration, iteration_dir)
        save_experiment_record(experiment_memory, record)
        state["experiment_memory"]["loaded_experiments"] = len(
            experiment_memory["experiments"]
        )
        state["experiment_memory"]["latest_experiment_id"] = record["id"]
        write_json(run_dir / "state.json", state)
        progress_agent(state, run_dir)

    if state["current_error"] <= target_error:
        state["status"] = "target_reached"
    elif state["accepted_iterations"] > 0:
        state["status"] = "iteration_limit_reached"
    else:
        state["status"] = "no_improvement_accepted"
    write_json(run_dir / "state.json", state)
    progress_agent(state, run_dir)

    console()
    console(f"多 Agent 迭代结束：{state['status']}")
    console(f"初始误差：{state['initial_error']}")
    console(f"当前误差：{state['current_error']}")
    console(f"接受迭代：{state['accepted_iterations']}")
    console(f"报告：{(run_dir / 'summary.md').relative_to(ROOT)}")
    return 0 if state["accepted_iterations"] > 0 or state["current_error"] <= target_error else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="运行正式多 Agent 数值迭代闭环。")
    parser.add_argument("--max-iterations", type=int, default=3, help="最大迭代次数，默认 3。")
    parser.add_argument("--target-error", type=float, default=0.01, help="Frobenius 相对误差目标，默认 0.01。")
    args = parser.parse_args()
    if args.max_iterations <= 0:
        parser.error("--max-iterations 必须大于 0")
    if not 0.0 < args.target_error < 1.0:
        parser.error("--target-error 必须在 (0, 1) 内")
    return run_workflow(args.max_iterations, args.target_error)


if __name__ == "__main__":
    raise SystemExit(main())

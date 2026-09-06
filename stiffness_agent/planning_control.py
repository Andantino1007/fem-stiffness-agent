"""规划代次重置和只规划运行。"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .api_check import perform_api_check
from .project_config import ProjectConfig, load_project_config
from .verification import ROOT


MEMORY_PATH = ROOT / "build" / "workflow" / "experiment-memory.json"
PLANNING_STATE_PATH = ROOT / "build" / "workflow" / "planning-state.json"
ARCHIVE_ROOT = ROOT / "build" / "workflow" / "archive"
PLANS_ROOT = ROOT / "build" / "workflow" / "plans"
LATEST_REPORT_PATH = ROOT / "docs" / "verification" / "智能体最新迭代报告.md"
PROGRESS_PATH = ROOT / "docs" / "项目进度与下一步.md"
PROGRESS_LOG_PATH = ROOT / "docs" / "verification" / "项目进度日志.md"
STATUS_START = "<!-- AGENT_WORKFLOW_STATUS_START -->"
STATUS_END = "<!-- AGENT_WORKFLOW_STATUS_END -->"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _archived_lessons(memory: dict[str, Any]) -> list[dict[str, Any]]:
    """保留历史证据，但不把旧补丁指纹带入新代次硬门禁。"""
    lessons: list[dict[str, Any]] = []
    for item in memory.get("experiments", []):
        if not isinstance(item, dict):
            continue
        plan = item.get("experiment_plan", {})
        experiment_class = (
            str(plan.get("experiment_class", "")) if isinstance(plan, dict) else ""
        )
        lessons.append(
            {
                "id": str(item.get("id", "historical-experiment")),
                "experiment_class": experiment_class,
                "accepted": bool(item.get("accepted", False)),
                "failure_mechanism": str(item.get("failure_mechanism", ""))[:1000],
                "do_not_repeat": [
                    str(value)[:500]
                    for value in item.get("do_not_repeat", [])
                    if isinstance(value, str) and value.strip()
                ],
                "next_focus": str(item.get("next_focus", ""))[:1000],
            }
        )
    return lessons[-40:]


def _replace_progress_status(project: ProjectConfig, generation: int, reason: str) -> None:
    if not PROGRESS_PATH.is_file():
        return
    text = PROGRESS_PATH.read_text(encoding="utf-8")
    if STATUS_START not in text or STATUS_END not in text:
        return
    block = "\n".join(
        [
            STATUS_START,
            "### Agent 自动迭代状态",
            "",
            f"- 项目：`{project.project_id}`",
            f"- 单元类型：`{project.element_type}`",
            f"- 矩阵尺寸：`{project.matrix_size} x {project.matrix_size}`",
            f"- 规划代次：`{generation}`",
            "- 状态：`awaiting_replan`",
            f"- 重置原因：{reason}",
            "- 历史运行：已归档保留，不参与新代次 Duplicate Gate",
            STATUS_END,
        ]
    )
    pattern = re.compile(
        re.escape(STATUS_START) + r".*?" + re.escape(STATUS_END),
        flags=re.DOTALL,
    )
    PROGRESS_PATH.write_text(pattern.sub(block, text), encoding="utf-8")


def reset_planning(reason: str) -> dict[str, Any]:
    """归档当前活动记忆并开启空白规划代次，不删除历史运行。"""
    project = load_project_config()
    previous_state = _read_json(PLANNING_STATE_PATH)
    previous_memory = _read_json(MEMORY_PATH)
    lesson_source = previous_memory
    if not lesson_source.get("experiments") and isinstance(previous_state.get("archive"), str):
        archived_memory = (
            ROOT
            / str(previous_state["archive"])
            / "build"
            / "workflow"
            / "experiment-memory.json"
        )
        candidate = _read_json(archived_memory)
        if candidate.get("experiments"):
            lesson_source = candidate
    previous_generation = int(
        previous_state.get(
            "planning_generation", previous_memory.get("planning_generation", 0)
        )
        or 0
    )
    generation = previous_generation + 1
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    reset_at = datetime.now().astimezone().isoformat(timespec="seconds")
    archive_dir = ARCHIVE_ROOT / f"planning-generation-{generation - 1}-{timestamp}"
    archive_dir.mkdir(parents=True, exist_ok=False)
    archived: list[str] = []
    for source in (MEMORY_PATH, PLANNING_STATE_PATH, LATEST_REPORT_PATH):
        if source.is_file():
            destination = archive_dir / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            archived.append(str(source.relative_to(ROOT)))

    memory = {
        "schema_version": 2,
        "project_id": project.project_id,
        "planning_generation": generation,
        "reset_at": reset_at,
        "reset_reason": reason,
        "history_policy": "active_generation_only",
        "archived_lessons": _archived_lessons(lesson_source),
        "experiments": [],
    }
    state = {
        "schema_version": 1,
        "project_id": project.project_id,
        "element_type": project.element_type,
        "matrix_dimensions": list(project.matrix_dimensions),
        "planning_generation": generation,
        "status": "awaiting_replan",
        "reset_at": reset_at,
        "reset_reason": reason,
        "archive": str(archive_dir.relative_to(ROOT)),
        "archived_files": archived,
        "latest_plan": None,
    }
    _write_json(MEMORY_PATH, memory)
    _write_json(PLANNING_STATE_PATH, state)
    LATEST_REPORT_PATH.write_text(
        "\n".join(
            [
                "# Planner 状态",
                "",
                f"- Project: `{project.project_id}`",
                f"- Element type: `{project.element_type}`",
                f"- Matrix dimensions: `{project.matrix_size} x {project.matrix_size}`",
                f"- Planning generation: `{generation}`",
                "- Status: `awaiting_replan`",
                f"- Reset reason: {reason}",
                f"- Archive: `{archive_dir.relative_to(ROOT)}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _replace_progress_status(project, generation, reason)
    if PROGRESS_LOG_PATH.is_file():
        existing = PROGRESS_LOG_PATH.read_text(encoding="utf-8").rstrip()
        entry = "\n".join(
            [
                "",
                f"## {datetime.now().date().isoformat()}：规划代次重置为 `{generation}`",
                "",
                f"- 项目：`{project.project_id}`",
                "- 状态：`awaiting_replan`",
                f"- 原因：{reason}",
                f"- 归档：`{archive_dir.relative_to(ROOT)}`",
                "",
            ]
        )
        PROGRESS_LOG_PATH.write_text(existing + "\n" + entry, encoding="utf-8")
    return state


def reset_planning_command(reason: str) -> int:
    try:
        state = reset_planning(reason)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Planning reset failed: {exc}")
        return 4
    print(f"Planning generation: {state['planning_generation']}")
    print(f"Status: {state['status']}")
    print(f"Archive: {state['archive']}")
    return 0


def replan() -> tuple[int, Path | None]:
    """运行基线和 Experiment Planner；不调用 Developer，不修改实现源码。"""
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from model_api_client import load_openai_config
    from agent_workflow import (
        experiment_planner_agent,
        load_experiment_memory,
        run_verification,
        write_json,
    )

    project = load_project_config()
    planning_state = _read_json(PLANNING_STATE_PATH)
    generation = int(planning_state.get("planning_generation", 0) or 0)
    if generation <= 0:
        raise ValueError("尚未建立规划代次，请先运行 reset-plan")

    run_id = datetime.now().strftime(f"replan-g{generation}-%Y%m%d-%H%M%S")
    plan_dir = PLANS_ROOT / run_id
    plan_dir.mkdir(parents=True, exist_ok=False)
    try:
        preflight = perform_api_check()
        write_json(plan_dir / "api-preflight.json", preflight)
        baseline = run_verification(plan_dir, "baseline")
        if baseline.get("exit_code") != 0:
            raise RuntimeError(f"基线验证失败：{baseline.get('log')}")
        memory = load_experiment_memory()
        current_error = baseline["metrics"]["frobenius_relative_error"]
        state = {
            "run_id": run_id,
            "runtime": f"openai:{load_openai_config().model}",
            "target_error": project.acceptance["target_error"],
            "max_iterations": 1,
            "initial_error": current_error,
            "current_error": current_error,
            "accepted_iterations": 0,
            "status": "planning",
            "current_verification": baseline,
            "iteration_number": 1,
            "planning_attempt": 1,
            "planning_generation": generation,
            "planning_objective": planning_state.get("reset_reason", "重新规划"),
            "project_id": project.project_id,
        }
        plan, _ = experiment_planner_agent(state, plan_dir, "", memory)
        summary = {
            "schema_version": 1,
            "project_id": project.project_id,
            "planning_generation": generation,
            "run_id": run_id,
            "status": "planned",
            "baseline_error": current_error,
            "plan": plan,
        }
        write_json(plan_dir / "summary.json", summary)
        planning_state.update(
            {
                "status": "planned",
                "planned_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "baseline_error": current_error,
                "latest_plan": str((plan_dir / "experiment-plan.json").relative_to(ROOT)),
                "latest_plan_run": run_id,
            }
        )
        planning_state.pop("last_error", None)
        planning_state.pop("last_attempt", None)
        _write_json(PLANNING_STATE_PATH, planning_state)
        LATEST_REPORT_PATH.write_text(
            "\n".join(
                [
                    "# Planner 重新规划结果",
                    "",
                    f"- Project: `{project.project_id}`",
                    f"- Element type: `{project.element_type}`",
                    f"- Matrix dimensions: `{project.matrix_size} x {project.matrix_size}`",
                    f"- Planning generation: `{generation}`",
                    "- Status: `planned`",
                    f"- Baseline error: `{current_error}`",
                    f"- Plan: `{(plan_dir / 'experiment-plan.json').relative_to(ROOT)}`",
                    "",
                    "## 新计划",
                    "",
                    f"- Hypothesis: `{plan['hypothesis_id']}`",
                    f"- Experiment class: `{plan['experiment_class']}`",
                    f"- Primary metric: `{plan['primary_metric']}`",
                    f"- Mechanism: {plan['mechanism']}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        if PROGRESS_PATH.is_file():
            text = PROGRESS_PATH.read_text(encoding="utf-8")
            block = "\n".join(
                [
                    STATUS_START,
                    "### Agent 自动迭代状态",
                    "",
                    f"- 项目：`{project.project_id}`",
                    f"- 单元类型：`{project.element_type}`",
                    f"- 矩阵尺寸：`{project.matrix_size} x {project.matrix_size}`",
                    f"- 规划代次：`{generation}`",
                    "- 状态：`planned`",
                    f"- 基线误差：`{current_error}`",
                    f"- 最新计划：`{(plan_dir / 'experiment-plan.json').relative_to(ROOT)}`",
                    f"- 假设：`{plan['hypothesis_id']}`",
                    STATUS_END,
                ]
            )
            pattern = re.compile(
                re.escape(STATUS_START) + r".*?" + re.escape(STATUS_END),
                flags=re.DOTALL,
            )
            PROGRESS_PATH.write_text(pattern.sub(block, text), encoding="utf-8")
        return 0, plan_dir / "experiment-plan.json"
    except Exception as exc:
        planning_state.update(
            {
                "status": "replan_failed",
                "last_error": str(exc),
                "last_attempt": run_id,
            }
        )
        _write_json(PLANNING_STATE_PATH, planning_state)
        (plan_dir / "error.txt").write_text(str(exc) + "\n", encoding="utf-8")
        print(f"Replan failed: {exc}")
        return 3, None


def replan_command() -> int:
    try:
        code, plan_path = replan()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Replan failed: {exc}")
        return 4
    if plan_path is not None:
        print(f"Planner completed: {plan_path.relative_to(ROOT)}")
    return code

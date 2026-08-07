#!/usr/bin/env python3
"""使用 LangGraph 编排在线多 Agent 数值迭代。"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from shell_agent.api_check import perform_api_check
from agent_openai_client import OpenAIClientError, OpenAIHttpError, load_openai_config
from agents import (
    EXPERIMENT_MEMORY_PATH,
    ROOT,
    RUNS_DIR,
    SOURCE_PATH,
    apply_unified_diff,
    build_experiment_record,
    compare_expected_metrics,
    console,
    developer_patch_with_retry,
    experiment_planner_agent,
    find_duplicate_patch,
    load_experiment_memory,
    progress_agent,
    reviewer_agent,
    run_verification,
    save_experiment_record,
    theory_agent,
    write_json,
    write_text,
)

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import RetryPolicy
except ImportError as exc:
    raise SystemExit(
        "缺少 LangGraph 依赖。请使用 Python 3.10+ 执行：\n"
        "python -m pip install -r requirements-langgraph.txt"
    ) from exc


CHECKPOINT_PATH = ROOT / "workflow" / "checkpoints" / "checkpoint.sqlite"


class GraphState(TypedDict, total=False):
    run_id: str
    run_dir: str
    runtime: str
    target_error: float
    max_iterations: int
    initial_error: float
    current_error: float
    accepted_iterations: int
    status: str
    current_verification: dict[str, Any]
    experiment_memory: dict[str, Any]
    experiment_plan: dict[str, Any]
    iterations: list[dict[str, Any]]
    iteration_number: int
    iteration: dict[str, Any]
    planning_attempt: int
    attempted_patch_fingerprints: list[str]
    previous_feedback: str
    theory_output: str
    developer_diff: str
    infrastructure_error: str
    api_preflight: dict[str, Any]


def state_run_dir(state: GraphState) -> Path:
    return ROOT / state["run_dir"]


def state_iteration_dir(state: GraphState) -> Path:
    return state_run_dir(state) / f"iteration-{state['iteration_number']:02d}"


def is_retryable_api_error(exc: Exception) -> bool:
    if isinstance(exc, OpenAIHttpError):
        return exc.status_code == 429 or exc.status_code >= 500
    return isinstance(exc, OpenAIClientError)


API_RETRY_POLICY = RetryPolicy(
    initial_interval=5.0,
    backoff_factor=2.0,
    max_interval=60.0,
    max_attempts=4,
    jitter=True,
    retry_on=is_retryable_api_error,
)


def api_preflight_node(state: GraphState) -> dict[str, Any]:
    console("[LangGraph] API Preflight：检查网关、模型和接口")
    return {
        "api_preflight": perform_api_check(),
        "infrastructure_error": "",
    }


def coordinator_node(state: GraphState) -> dict[str, Any]:
    console("[LangGraph] Coordinator：运行基线验证并加载长期记忆")
    run_dir = state_run_dir(state)
    run_dir.mkdir(parents=True, exist_ok=True)
    baseline = run_verification(run_dir, "baseline")
    if baseline["exit_code"] != 0:
        raise RuntimeError(f"基线验证失败，见 {baseline['log']}")

    memory = load_experiment_memory()
    write_json(EXPERIMENT_MEMORY_PATH, memory)
    initial_error = baseline["metrics"]["frobenius_relative_error"]
    updated = {
        **state,
        "initial_error": initial_error,
        "current_error": initial_error,
        "accepted_iterations": 0,
        "status": "running",
        "current_verification": baseline,
        "experiment_memory": memory,
        "iterations": [],
        "iteration_number": 1,
        "planning_attempt": 0,
        "attempted_patch_fingerprints": [],
        "previous_feedback": "",
        "infrastructure_error": "",
    }
    write_json(run_dir / "state.json", updated)
    return updated


def planner_node(state: GraphState) -> dict[str, Any]:
    number = state["iteration_number"]
    runtime = f"openai:{load_openai_config().model}"
    planner_state = {**state, "runtime": runtime}
    iteration_dir = state_iteration_dir(state)
    iteration_dir.mkdir(parents=True, exist_ok=True)
    backup_path = iteration_dir / "ShellStiffness.cpp.before"
    if not backup_path.exists():
        shutil.copy2(SOURCE_PATH, backup_path)
    attempt = state.get("planning_attempt", 0) + 1
    console(
        f"[{number}/{state['max_iterations']}] "
        f"Experiment Planner：规划实验（尝试 {attempt}）"
    )
    plan, _ = experiment_planner_agent(
        planner_state,
        iteration_dir,
        state.get("previous_feedback", ""),
        state["experiment_memory"],
    )
    shutil.copy2(
        iteration_dir / "experiment-planner-response.md",
        iteration_dir / f"experiment-planner-response-{attempt}.md",
    )
    shutil.copy2(
        iteration_dir / "experiment-plan.json",
        iteration_dir / f"experiment-plan-{attempt}.json",
    )
    iteration = dict(state.get("iteration", {}))
    iteration.update(
        {
            "iteration": number,
            "before_error": state["current_error"],
            "experiment_plan": plan,
            "planning_attempt": attempt,
        }
    )
    return {
        "experiment_plan": plan,
        "iteration": iteration,
        "planning_attempt": attempt,
        "runtime": runtime,
        "infrastructure_error": "",
    }


def theory_node(state: GraphState) -> dict[str, Any]:
    number = state["iteration_number"]
    iteration_dir = state_iteration_dir(state)
    console(f"[{number}/{state['max_iterations']}] Theory Research Agent")
    output = theory_agent(
        state,
        iteration_dir,
        state.get("previous_feedback", ""),
        state["experiment_memory"],
        state["experiment_plan"],
    )
    attempt = state.get("planning_attempt", 1)
    shutil.copy2(
        iteration_dir / "theory-analysis.md",
        iteration_dir / f"theory-analysis-{attempt}.md",
    )
    return {
        "theory_output": output,
        "iteration": dict(state["iteration"]),
        "infrastructure_error": "",
    }


def developer_node(state: GraphState) -> dict[str, Any]:
    number = state["iteration_number"]
    console(f"[{number}/{state['max_iterations']}] Developer Agent")
    iteration = dict(state["iteration"])
    try:
        diff, patch_paths = developer_patch_with_retry(
            state,
            state["theory_output"],
            state_iteration_dir(state),
            state.get("previous_feedback", ""),
            state["experiment_memory"],
            state["experiment_plan"],
        )
        iteration["patch_paths"] = patch_paths
        return {
            "developer_diff": diff,
            "iteration": iteration,
            "infrastructure_error": "",
        }
    except OpenAIClientError:
        raise
    except Exception as exc:
        iteration["patch_applied"] = False
        iteration["failure"] = str(exc)
        return {"developer_diff": "", "iteration": iteration}


def duplicate_gate_node(state: GraphState) -> dict[str, Any]:
    """在编译前拦截语义相同的历史补丁或当前运行重复尝试。"""
    number = state["iteration_number"]
    console(f"[{number}/{state['max_iterations']}] Duplicate Gate：检查重复补丁")
    iteration_dir = state_iteration_dir(state)
    diff = state.get("developer_diff", "")
    if diff:
        write_text(iteration_dir / "developer.patch", diff)
        write_text(
            iteration_dir / f"developer-patch-attempt-{state.get('planning_attempt', 1)}.patch",
            diff,
        )

    attempted = list(state.get("attempted_patch_fingerprints", []))
    fingerprint, matches = find_duplicate_patch(
        diff,
        state["experiment_memory"],
        attempted,
    )
    iteration = dict(state["iteration"])
    iteration["patch_fingerprint"] = fingerprint
    iteration["duplicate_patch"] = bool(matches)
    iteration["duplicate_matches"] = matches
    if fingerprint and fingerprint not in attempted:
        attempted.append(fingerprint)

    feedback = state.get("previous_feedback", "")
    if matches:
        message = (
            "本地 Duplicate Gate 拒绝候选：补丁与已失败实验语义重复，"
            f"命中 {matches}。Planner 必须选择不同机理和实际代码修改。"
        )
        iteration["failure"] = message
        iteration["patch_applied"] = False
        feedback = message
        console(f"[DUPLICATE] {message}")

    write_json(
        iteration_dir / f"duplicate-gate-{state.get('planning_attempt', 1)}.json",
        {
            "patch_fingerprint": fingerprint,
            "duplicate": bool(matches),
            "matches": matches,
        },
    )
    return {
        "iteration": iteration,
        "attempted_patch_fingerprints": attempted,
        "previous_feedback": feedback,
    }


def duplicate_reject_node(state: GraphState) -> dict[str, Any]:
    """连续重复达到上限时本地拒绝，避免浪费 Test 和 Reviewer API。"""
    iteration = dict(state["iteration"])
    matches = iteration.get("duplicate_matches", [])
    message = (
        f"连续 {state.get('planning_attempt', 0)} 次规划仍生成重复补丁，"
        f"本轮由本地闸门拒绝；命中 {matches}。"
    )
    iteration.update(
        {
            "patch_applied": False,
            "test_passed": False,
            "candidate_error": None,
            "reviewer_decision": "local_reject",
            "reviewer_summary": message,
            "failure_mechanism": "Experiment Planner 和 Developer 未避开已失败补丁",
            "do_not_repeat": ["不得再次生成相同语义补丁"],
            "next_focus": "选择不同 experiment_class 或具有实质差异的公式修改",
            "local_improvement_gate": False,
            "accepted": False,
        }
    )
    console(f"[REJECTED] {message}")
    return {"iteration": iteration}


def candidate_test_node(state: GraphState) -> dict[str, Any]:
    """应用候选、测试并立即恢复，保证 API 暂停时工作区仍是有效版本。"""
    number = state["iteration_number"]
    console(f"[{number}/{state['max_iterations']}] Patch Validate + Test Agent")
    iteration_dir = state_iteration_dir(state)
    backup_path = iteration_dir / "ShellStiffness.cpp.before"
    iteration = dict(state["iteration"])
    candidate: dict[str, Any] = {"exit_code": -1}

    try:
        if not state.get("developer_diff"):
            iteration.setdefault("patch_applied", False)
            iteration.setdefault("failure", "Developer Agent 未生成有效补丁")
        else:
            apply_result = apply_unified_diff(state["developer_diff"], iteration_dir)
            iteration["patch_applied"] = apply_result["applied"]
            if apply_result["applied"]:
                candidate = run_verification(iteration_dir, "candidate")
            else:
                iteration["failure"] = apply_result["reason"]
    finally:
        shutil.copy2(backup_path, SOURCE_PATH)
        restored = run_verification(iteration_dir, "restored")
        if restored["exit_code"] != 0:
            raise RuntimeError("恢复上一有效版本后验证失败")

    iteration["test_passed"] = candidate.get("exit_code") == 0
    if "metrics" in candidate:
        iteration["candidate_error"] = candidate["metrics"]["frobenius_relative_error"]
        iteration["candidate_metrics"] = candidate["metrics"]
        iteration["candidate_diagnostics"] = candidate.get("diagnostics", {})
        iteration["expected_metric_comparison"] = compare_expected_metrics(
            list(state["experiment_plan"]["expected_metrics"]),
            state["current_verification"],
            candidate,
        )
        iteration["expected_metrics_available"] = True
    else:
        iteration["candidate_error"] = None
        iteration["candidate_diagnostics"] = {}
        iteration["expected_metric_comparison"] = {}
        iteration["expected_metrics_available"] = False
    return {"iteration": iteration}


def reviewer_node(state: GraphState) -> dict[str, Any]:
    number = state["iteration_number"]
    console(f"[{number}/{state['max_iterations']}] Reviewer Agent")
    review, raw_review = reviewer_agent(
        state,
        state["iteration"],
        state_iteration_dir(state),
        state["experiment_memory"],
    )
    iteration = dict(state["iteration"])
    iteration["reviewer_decision"] = str(review.get("decision", "reject")).lower()
    iteration["reviewer_summary"] = str(review.get("summary", ""))
    iteration["failure_mechanism"] = str(review.get("failure_mechanism", ""))
    do_not_repeat = review.get("do_not_repeat", [])
    if isinstance(do_not_repeat, str):
        do_not_repeat = [do_not_repeat] if do_not_repeat.strip() else []
    iteration["do_not_repeat"] = do_not_repeat if isinstance(do_not_repeat, list) else []
    iteration["next_focus"] = str(review.get("next_focus", ""))
    return {
        "iteration": iteration,
        "previous_feedback": raw_review,
        "infrastructure_error": "",
    }


def decision_node(state: GraphState) -> dict[str, Any]:
    """执行本地硬门槛；接受时重新应用已测试补丁并复验。"""
    iteration = dict(state["iteration"])
    candidate_error = iteration.get("candidate_error")
    improved = bool(
        iteration.get("test_passed")
        and iteration.get("expected_metrics_available")
        and candidate_error is not None
        and candidate_error < state["current_error"] - 1.0e-9
    )
    accepted = improved and iteration.get("reviewer_decision") == "accept"
    iteration["local_improvement_gate"] = improved
    iteration["accepted"] = accepted

    updates: dict[str, Any] = {"iteration": iteration}
    if not accepted:
        console(
            f"[REJECTED] {iteration.get('reviewer_summary', iteration.get('failure', '未改善'))}"
        )
        return updates

    iteration_dir = state_iteration_dir(state)
    backup_path = iteration_dir / "ShellStiffness.cpp.before"
    apply_result = apply_unified_diff(state["developer_diff"], iteration_dir)
    committed = run_verification(iteration_dir, "committed") if apply_result["applied"] else {"exit_code": -1}
    if committed.get("exit_code") != 0:
        shutil.copy2(backup_path, SOURCE_PATH)
        run_verification(iteration_dir, "commit-restored")
        iteration["accepted"] = False
        iteration["failure"] = "接受后重新应用或复验失败"
        console("[REJECTED] 接受后重新应用或复验失败，已恢复")
        return {"iteration": iteration}

    committed_error = committed["metrics"]["frobenius_relative_error"]
    if abs(committed_error - float(candidate_error)) > 1.0e-9:
        shutil.copy2(backup_path, SOURCE_PATH)
        run_verification(iteration_dir, "commit-restored")
        iteration["accepted"] = False
        iteration["failure"] = "提交复验误差与候选误差不一致"
        console("[REJECTED] 提交复验不一致，已恢复")
        return {"iteration": iteration}

    console(f"[ACCEPTED] 误差降至 {committed_error}")
    updates.update(
        {
            "current_error": committed_error,
            "current_verification": committed,
            "accepted_iterations": state["accepted_iterations"] + 1,
            "iteration": iteration,
        }
    )
    return updates


def record_node(state: GraphState) -> dict[str, Any]:
    iteration = dict(state["iteration"])
    memory = dict(state["experiment_memory"])
    memory["experiments"] = list(memory.get("experiments", []))
    record = build_experiment_record(
        state["run_id"], iteration, state_iteration_dir(state)
    )
    save_experiment_record(memory, record)
    iterations = list(state.get("iterations", []))
    iterations.append(iteration)

    updated = {
        **state,
        "experiment_memory": memory,
        "iterations": iterations,
        "iteration_number": state["iteration_number"] + 1,
        "experiment_plan": {},
        "planning_attempt": 0,
        "theory_output": "",
        "developer_diff": "",
        "iteration": {},
    }
    write_json(state_run_dir(state) / "state.json", updated)
    progress_agent(updated, state_run_dir(state))
    return {
        "experiment_memory": memory,
        "iterations": iterations,
        "iteration_number": state["iteration_number"] + 1,
        "experiment_plan": {},
        "planning_attempt": 0,
        "theory_output": "",
        "developer_diff": "",
        "iteration": {},
    }


def finalize_node(state: GraphState) -> dict[str, Any]:
    if state["current_error"] <= state["target_error"]:
        status = "target_reached"
    elif state["accepted_iterations"] > 0:
        status = "iteration_limit_reached"
    else:
        status = "no_improvement_accepted"
    updated = {**state, "status": status}
    write_json(state_run_dir(state) / "state.json", updated)
    progress_agent(updated, state_run_dir(state))
    console(f"LangGraph 工作流结束：{status}")
    console(f"当前误差：{state['current_error']}")
    return {"status": status}


def route_after_coordinator(state: GraphState) -> str:
    if state["current_error"] <= state["target_error"]:
        return "finalize"
    return "planner"


def route_after_record(state: GraphState) -> str:
    if state["current_error"] <= state["target_error"]:
        return "finalize"
    if state["iteration_number"] > state["max_iterations"]:
        return "finalize"
    return "planner"


def route_after_duplicate_gate(state: GraphState) -> str:
    if not state["iteration"].get("duplicate_patch", False):
        return "candidate_test"
    if state.get("planning_attempt", 0) < 3:
        return "planner"
    return "duplicate_reject"


def build_graph(checkpointer: SqliteSaver):
    graph = StateGraph(GraphState)
    graph.add_node("api_preflight", api_preflight_node, retry_policy=API_RETRY_POLICY)
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("planner", planner_node, retry_policy=API_RETRY_POLICY)
    graph.add_node("theory", theory_node, retry_policy=API_RETRY_POLICY)
    graph.add_node("developer", developer_node, retry_policy=API_RETRY_POLICY)
    graph.add_node("duplicate_gate", duplicate_gate_node)
    graph.add_node("duplicate_reject", duplicate_reject_node)
    graph.add_node("candidate_test", candidate_test_node)
    graph.add_node("reviewer", reviewer_node, retry_policy=API_RETRY_POLICY)
    graph.add_node("decision", decision_node)
    graph.add_node("record", record_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "api_preflight")
    graph.add_edge("api_preflight", "coordinator")
    graph.add_conditional_edges(
        "coordinator",
        route_after_coordinator,
        {"planner": "planner", "finalize": "finalize"},
    )
    graph.add_edge("planner", "theory")
    graph.add_edge("theory", "developer")
    graph.add_edge("developer", "duplicate_gate")
    graph.add_conditional_edges(
        "duplicate_gate",
        route_after_duplicate_gate,
        {
            "planner": "planner",
            "candidate_test": "candidate_test",
            "duplicate_reject": "duplicate_reject",
        },
    )
    graph.add_edge("duplicate_reject", "record")
    graph.add_edge("candidate_test", "reviewer")
    graph.add_edge("reviewer", "decision")
    graph.add_edge("decision", "record")
    graph.add_conditional_edges(
        "record",
        route_after_record,
        {"planner": "planner", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)


def status_path(run_id: str) -> Path:
    return RUNS_DIR / run_id / "langgraph-status.json"


def initial_state(run_id: str, max_iterations: int, target_error: float) -> GraphState:
    cfg = load_openai_config()
    return {
        "run_id": run_id,
        "run_dir": str((RUNS_DIR / run_id).relative_to(ROOT)),
        "runtime": f"openai:{cfg.model}",
        "target_error": target_error,
        "max_iterations": max_iterations,
        "status": "initializing",
    }


def run_graph(
    graph,
    config: dict[str, Any],
    graph_input: GraphState | None,
    run_id: str,
) -> int:
    try:
        for update in graph.stream(
            graph_input,
            config,
            stream_mode="updates",
        ):
            for node_name in update:
                console(f"[checkpoint] {node_name}")
        snapshot = graph.get_state(config)
        state = snapshot.values
        write_json(
            status_path(run_id),
            {
                "run_id": run_id,
                "status": state.get("status", "completed"),
                "next_nodes": list(snapshot.next),
                "error": "",
            },
        )
        return 0 if state.get("accepted_iterations", 0) > 0 or state.get("current_error", 1.0) <= state.get("target_error", 0.01) else 2
    except Exception as exc:
        snapshot = graph.get_state(config)
        write_json(
            status_path(run_id),
            {
                "run_id": run_id,
                "status": "paused_on_error",
                "next_nodes": list(snapshot.next),
                "error": str(exc),
            },
        )
        console(f"[PAUSED] 节点执行失败，checkpoint 已保存：{exc}")
        console(f"恢复命令：python -m shell_agent resume {run_id}")
        return 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行 LangGraph 多 Agent 工作流。")
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--target-error", type=float, default=0.01)
    parser.add_argument("--resume", metavar="RUN_ID", help="从 SQLite checkpoint 恢复指定 run。")
    parser.add_argument("--check", action="store_true", help="只检查 LangGraph 环境和图编译，不调用 API。")
    args = parser.parse_args(argv)
    if args.max_iterations <= 0:
        parser.error("--max-iterations 必须大于 0")
    if not 0.0 < args.target_error < 1.0:
        parser.error("--target-error 必须在 (0, 1) 内")

    if args.check:
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            graph = build_graph(checkpointer)
            node_count = len(graph.get_graph().nodes)
        console(f"Python：{sys.version.split()[0]}")
        console(f"LangGraph：{importlib.metadata.version('langgraph')}")
        console(
            "LangGraph SQLite："
            f"{importlib.metadata.version('langgraph-checkpoint-sqlite')}"
        )
        console(f"Graph nodes：{node_count}")
        console("LangGraph environment check passed.")
        return 0

    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    run_id = args.resume or datetime.now().strftime("run-%Y%m%d-%H%M%S")
    config = {"configurable": {"thread_id": run_id}}
    graph_input = None if args.resume else initial_state(run_id, args.max_iterations, args.target_error)

    console(f"LangGraph thread_id：{run_id}")
    with SqliteSaver.from_conn_string(str(CHECKPOINT_PATH)) as checkpointer:
        graph = build_graph(checkpointer)
        if args.resume:
            snapshot = graph.get_state(config)
            if not snapshot.values:
                console(f"找不到 checkpoint：{run_id}")
                return 4
            console(f"从节点恢复：{list(snapshot.next)}")
        return run_graph(graph, config, graph_input, run_id)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""LangGraph 编排的离线测试，不调用 API。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from agent_openai_client import OpenAIClientError, OpenAIHttpError
from graph import (
    build_graph,
    is_retryable_api_error,
    route_after_duplicate_gate,
    route_after_record,
)
from langgraph.checkpoint.sqlite import SqliteSaver


class GraphWorkflowTests(unittest.TestCase):
    def test_retries_connection_and_temporary_http_errors(self) -> None:
        self.assertTrue(is_retryable_api_error(OpenAIClientError("断开连接")))
        self.assertTrue(is_retryable_api_error(OpenAIHttpError(503, "暂时不可用")))
        self.assertTrue(is_retryable_api_error(OpenAIHttpError(429, "限流")))
        self.assertFalse(is_retryable_api_error(OpenAIHttpError(400, "请求错误")))

    def test_routes_to_next_iteration_or_finalize(self) -> None:
        continuing = {
            "current_error": 0.14,
            "target_error": 0.01,
            "iteration_number": 2,
            "max_iterations": 3,
        }
        self.assertEqual(route_after_record(continuing), "planner")

        exhausted = {**continuing, "iteration_number": 4}
        self.assertEqual(route_after_record(exhausted), "finalize")

        reached = {**continuing, "current_error": 0.009}
        self.assertEqual(route_after_record(reached), "finalize")

    def test_duplicate_gate_replans_before_local_rejection(self) -> None:
        duplicate = {
            "iteration": {"duplicate_patch": True},
            "planning_attempt": 1,
        }
        self.assertEqual(route_after_duplicate_gate(duplicate), "planner")
        exhausted = {**duplicate, "planning_attempt": 3}
        self.assertEqual(route_after_duplicate_gate(exhausted), "duplicate_reject")
        unique = {
            "iteration": {"duplicate_patch": False},
            "planning_attempt": 1,
        }
        self.assertEqual(route_after_duplicate_gate(unique), "candidate_test")

    def test_compiles_expected_graph_nodes(self) -> None:
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            graph = build_graph(checkpointer)
            nodes = set(graph.get_graph().nodes)
        expected = {
            "api_preflight",
            "coordinator",
            "planner",
            "theory",
            "developer",
            "duplicate_gate",
            "duplicate_reject",
            "candidate_test",
            "reviewer",
            "decision",
            "record",
            "finalize",
        }
        self.assertTrue(expected.issubset(nodes))


if __name__ == "__main__":
    unittest.main()

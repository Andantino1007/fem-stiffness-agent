#!/usr/bin/env python3
"""Agent 迭代器的离线安全测试，不调用 API。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from agents import (
    agent_state_snapshot,
    build_experiment_record,
    compare_expected_metrics,
    evaluate_candidate_gate,
    extract_json_object,
    extract_unified_diff,
    find_duplicate_patch,
    patch_fingerprint,
    render_experiment_memory,
    save_experiment_record,
    update_progress_overview_status,
    validate_experiment_plan,
    validate_unified_diff,
)


class AgentWorkflowTests(unittest.TestCase):
    def test_agent_state_snapshot_excludes_large_repeated_payloads(self) -> None:
        state = {
            "run_id": "run-test",
            "runtime": "openai:gpt-5.5",
            "current_error": 0.14,
            "current_verification": {
                "metrics": {"frobenius_relative_error": 0.14},
                "diagnostics": {"large": "x" * 10000},
            },
            "experiment_memory": {"experiments": [{"large": "x" * 10000}]},
            "iterations": [{"large": "x" * 10000}],
        }
        snapshot = agent_state_snapshot(state)
        self.assertEqual(snapshot["run_id"], "run-test")
        self.assertIn("current_metrics", snapshot)
        self.assertNotIn("experiment_memory", snapshot)
        self.assertNotIn("iterations", snapshot)
        self.assertNotIn("diagnostics", snapshot)

    def test_extracts_and_validates_allowed_patch(self) -> None:
        response = """BEGIN_UNIFIED_DIFF
--- a/src/shell/ShellStiffness.cpp
+++ b/src/shell/ShellStiffness.cpp
@@ -1,1 +1,1 @@
-old
+new
END_UNIFIED_DIFF"""
        diff = extract_unified_diff(response)
        self.assertEqual(validate_unified_diff(diff), ["src/shell/ShellStiffness.cpp"])

    def test_rejects_test_file_patch(self) -> None:
        diff = """--- a/tests/forbidden_tests.cpp
+++ b/tests/forbidden_tests.cpp
@@ -1,1 +1,1 @@
-old
+new
"""
        with self.assertRaises(ValueError):
            validate_unified_diff(diff)

    def test_rejects_dangerous_added_call(self) -> None:
        diff = """--- a/src/shell/ShellStiffness.cpp
+++ b/src/shell/ShellStiffness.cpp
@@ -1,1 +1,1 @@
-old
+system(\"unsafe\");
"""
        with self.assertRaises(ValueError):
            validate_unified_diff(diff)

    def test_rejects_unclosed_diff_protocol(self) -> None:
        response = """BEGIN_UNIFIED_DIFF
--- a/src/shell/ShellStiffness.cpp
+++ b/src/shell/ShellStiffness.cpp
@@ -1,1 +1,1 @@
-old
+new
*** End Patch"""
        with self.assertRaises(ValueError):
            extract_unified_diff(response)

    def test_extracts_reviewer_json(self) -> None:
        payload = extract_json_object(
            '{"decision":"reject","summary":"误差上升",'
            '"failure_mechanism":"剪切过硬",'
            '"do_not_repeat":["四边中点直接积分"],'
            '"next_focus":"检查自由度符号"}'
        )
        self.assertEqual(payload["decision"], "reject")
        self.assertEqual(payload["do_not_repeat"], ["四边中点直接积分"])

    def test_validates_structured_experiment_plan(self) -> None:
        plan = {
            "hypothesis_id": "membrane-001",
            "experiment_class": "membrane",
            "target_block": "membrane_xy",
            "mechanism": "核对平面应力本构系数",
            "primary_metric": "membrane_xy__membrane_xy",
            "allowed_changes": ["膜本构矩阵"],
            "forbidden_changes": ["剪切符号"],
            "expected_metrics": [
                "frobenius_relative_error",
                "membrane_xy__membrane_xy",
            ],
            "difference_from_history": "历史尚未单独验证该系数",
        }
        self.assertEqual(validate_experiment_plan(plan), plan)
        with self.assertRaises(ValueError):
            validate_experiment_plan({**plan, "experiment_class": "unknown"})
        with self.assertRaises(ValueError):
            validate_experiment_plan({**plan, "expected_metrics": ["unknown metric"]})
        with self.assertRaises(ValueError):
            validate_experiment_plan({**plan, "expected_metrics": ["symmetry_error"]})

    def test_compares_declared_global_and_block_metrics(self) -> None:
        baseline = {
            "metrics": {"frobenius_relative_error": 0.10},
            "diagnostics": {
                "block_relative_errors": {"bending_shear__bending_shear": 0.30}
            },
        }
        candidate = {
            "metrics": {"frobenius_relative_error": 0.08},
            "diagnostics": {
                "block_relative_errors": {"bending_shear__bending_shear": 0.25}
            },
        }
        comparison = compare_expected_metrics(
            ["frobenius_relative_error", "bending_shear__bending_shear"],
            baseline,
            candidate,
        )
        self.assertTrue(comparison["frobenius_relative_error"]["improved"])
        self.assertAlmostEqual(
            comparison["bending_shear__bending_shear"]["delta"], -0.05
        )

    def test_candidate_gate_requires_meaningful_global_and_primary_improvement(self) -> None:
        block_keys = {
            f"{row}__{col}"
            for row in ("membrane_xy", "bending_shear", "drilling")
            for col in ("membrane_xy", "bending_shear", "drilling")
        }
        before_blocks = {key: 0.20 for key in block_keys}
        after_blocks = dict(before_blocks)
        after_blocks["bending_shear__bending_shear"] = 0.18
        baseline = {
            "metrics": {
                "frobenius_relative_error": 0.10,
                "max_absolute_error": 100.0,
                "symmetry_error": 1.0e-18,
            },
            "diagnostics": {"block_relative_errors": before_blocks},
        }
        candidate = {
            "metrics": {
                "frobenius_relative_error": 0.09,
                "max_absolute_error": 100.5,
                "symmetry_error": 1.0e-18,
            },
            "diagnostics": {"block_relative_errors": after_blocks},
        }
        gate = evaluate_candidate_gate(
            baseline, candidate, "bending_shear__bending_shear", True
        )
        self.assertTrue(gate["passed"])

        regressed = {
            **candidate,
            "diagnostics": {
                "block_relative_errors": {
                    **after_blocks,
                    "drilling__drilling": 0.22,
                }
            },
        }
        rejected = evaluate_candidate_gate(
            baseline, regressed, "bending_shear__bending_shear", True
        )
        self.assertFalse(rejected["passed"])
        self.assertIn("drilling__drilling", rejected["non_target_block_regressions"])

    def test_semantic_patch_fingerprint_ignores_comments_and_hunk_lines(self) -> None:
        first = """--- a/src/shell/ShellStiffness.cpp
+++ b/src/shell/ShellStiffness.cpp
@@ -10,3 +10,3 @@
-// 原注释
+// 新注释
-value = -shape[node];
+value = shape[node];
"""
        second = """--- a/src/shell/ShellStiffness.cpp
+++ b/src/shell/ShellStiffness.cpp
@@ -20,5 +20,5 @@
-// 另一种旧注释
+// 另一种新注释
-    value = -shape[node];
+    value = shape[node];
"""
        self.assertEqual(patch_fingerprint(first), patch_fingerprint(second))

    def test_finds_duplicate_patch_in_experiment_memory(self) -> None:
        diff = """--- a/src/shell/ShellStiffness.cpp
+++ b/src/shell/ShellStiffness.cpp
@@ -1,1 +1,1 @@
-old_value
+new_value
"""
        memory = {
            "experiments": [
                {
                    "id": "historical-run:iteration-01",
                    "patch_fingerprint": patch_fingerprint(diff),
                }
            ]
        }
        fingerprint, matches = find_duplicate_patch(diff, memory)
        self.assertEqual(fingerprint, patch_fingerprint(diff))
        self.assertEqual(matches, ["historical-run:iteration-01"])

    def test_builds_and_saves_cross_run_experiment_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            iteration_dir = Path(directory)
            (iteration_dir / "theory-analysis.md").write_text("历史检查后提出假设", encoding="utf-8")
            (iteration_dir / "developer.patch").write_text("示例补丁", encoding="utf-8")
            iteration = {
                "iteration": 2,
                "before_error": 0.14,
                "candidate_error": 0.19,
                "patch_applied": True,
                "test_passed": True,
                "accepted": False,
                "reviewer_decision": "reject",
                "reviewer_summary": "误差上升",
                "failure_mechanism": "剪切刚度过大",
                "do_not_repeat": ["四边中点直接积分"],
                "next_focus": "检查局部转角符号",
                "candidate_diagnostics": {
                    "block_relative_errors": {
                        "membrane_xy__membrane_xy": 0.08,
                        "bending_shear__bending_shear": 0.25,
                    }
                },
            }
            record = build_experiment_record("run-test", iteration, iteration_dir)
            memory = {"schema_version": 1, "experiments": []}
            memory_path = iteration_dir / "memory.json"
            save_experiment_record(memory, record, memory_path)

            self.assertTrue(memory_path.exists())
            self.assertEqual(memory["experiments"][0]["id"], "run-test:iteration-02")
            rendered = render_experiment_memory(memory)
            self.assertIn("四边中点直接积分", rendered)
            self.assertIn("剪切刚度过大", rendered)
            self.assertEqual(
                record["candidate_block_relative_errors"]["bending_shear__bending_shear"],
                0.25,
            )

    def test_updates_dedicated_progress_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            progress_path = Path(directory) / "PROJECT_PROGRESS.md"
            progress_path.write_text(
                "before\n<!-- AGENT_WORKFLOW_STATUS_START -->\nold\n"
                "<!-- AGENT_WORKFLOW_STATUS_END -->\nafter\n",
                encoding="utf-8",
            )
            state = {
                "run_id": "run-test",
                "status": "running",
                "initial_error": 0.14,
                "current_error": 0.12,
                "target_error": 0.01,
                "accepted_iterations": 1,
            }
            update_progress_overview_status(state, progress_path)
            content = progress_path.read_text(encoding="utf-8")
            self.assertIn("run-test", content)
            self.assertIn("当前误差：`0.12`", content)
            self.assertIn("before", content)
            self.assertIn("after", content)


if __name__ == "__main__":
    unittest.main()

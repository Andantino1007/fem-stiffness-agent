#!/usr/bin/env python3
"""统一 Python 命令行与验证驱动的离线测试。"""

from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from shell_agent.api_check import perform_api_check
from shell_agent.cli import build_parser
from shell_agent.verification import run_verification
from shell_agent.dataset_verification import load_dataset, summarize_split
from shell_agent.dataset_plan import validate_dataset_plan
from shell_agent.dataset_registry import check_test_lock, validate_sample_artifacts


class ShellAgentCliTests(unittest.TestCase):
    def test_parses_run_and_resume_commands(self) -> None:
        parser = build_parser()
        run = parser.parse_args(["run", "--max-iterations", "5", "--target-error", "0.02"])
        self.assertEqual(run.command, "run")
        self.assertEqual(run.max_iterations, 5)
        self.assertEqual(run.target_error, 0.02)

        resume = parser.parse_args(["resume", "run-test"])
        self.assertEqual(resume.command, "resume")
        self.assertEqual(resume.run_id, "run-test")

        api_check = parser.parse_args(["api-check"])
        self.assertEqual(api_check.command, "api-check")

        dataset = parser.parse_args(["verify-dataset", "--require-test"])
        self.assertEqual(dataset.command, "verify-dataset")
        self.assertTrue(dataset.require_test)

        plan = parser.parse_args(["validate-data-plan", "plan.json"])
        self.assertEqual(plan.command, "validate-data-plan")

        register = parser.parse_args(
            ["register-sample", "--meta", "sample.json", "--split", "validation"]
        )
        self.assertEqual(register.split, "validation")

        lock = parser.parse_args(["check-test-lock"])
        self.assertEqual(lock.command, "check-test-lock")

    @patch("shell_agent.verification.run_checked", side_effect=[0, 0, 0, 0])
    def test_verification_driver_uses_four_direct_process_calls(self, mocked_run) -> None:
        self.assertEqual(run_verification(), 0)
        self.assertEqual(mocked_run.call_count, 4)
        commands = [call.args[0] for call in mocked_run.call_args_list]
        self.assertTrue(any("src/shell_stiffness_cli.cpp" in command for command in commands))
        self.assertTrue(any("tests/shell_stiffness_tests.cpp" in command for command in commands))
        self.assertFalse(any(command and command[0] == "bash" for command in commands))

    @patch("shell_agent.api_check.call_openai_agent", return_value="API_OK")
    @patch("shell_agent.api_check.load_openai_config")
    def test_api_check_uses_real_client_contract(self, mocked_config, mocked_call) -> None:
        mocked_config.return_value.model = "test-model"
        mocked_config.return_value.base_url = "https://example.test/v1"
        mocked_config.return_value.api_style = "auto"
        result = perform_api_check()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["model"], "test-model")
        self.assertEqual(result["response_preview"], "API_OK")
        mocked_call.assert_called_once()

    def test_dataset_manifest_has_disjoint_train_and_test_splits(self) -> None:
        dataset = load_dataset()
        self.assertTrue(dataset["train"])
        membership = dataset["train"] + dataset["validation"] + dataset["test"]
        self.assertEqual(len(membership), len(set(membership)))
        self.assertFalse(summarize_split([])["ready"])

    def test_accepts_example_dataset_plan(self) -> None:
        plan = validate_dataset_plan(
            Path("data/datasets/plans/example_train_batch.json")
        )
        self.assertEqual(plan["split"], "train")
        self.assertEqual(plan["samples"][0]["sample_id"], "sample_002")

    def test_rejects_adaptive_test_plan(self) -> None:
        source = json.loads(
            Path("data/datasets/plans/example_train_batch.json").read_text(
                encoding="utf-8"
            )
        )
        source["split"] = "test"
        source["selection_policy"] = "coverage_driven"
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / "plan.json"
            plan_path.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_dataset_plan(plan_path)

    def test_validates_real_sample_and_reports_empty_test_lock(self) -> None:
        artifact = validate_sample_artifacts(
            Path("data/abaqus/meta/sample_001.json")
        )
        self.assertEqual(artifact["sample_id"], "sample_001")
        passed, message = check_test_lock()
        self.assertFalse(passed)
        self.assertIn("为空", message)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""统一 Python 命令行与验证驱动的离线测试。"""

from __future__ import annotations

import unittest
import csv
import json
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch

from stiffness_agent.api_check import perform_api_check
from stiffness_agent.cli import build_parser
from stiffness_agent.verification import evaluate_sample, prepare_adapter, run_verification
from stiffness_agent.dataset_verification import load_dataset, summarize_split
from stiffness_agent.dataset_plan import validate_dataset_plan
from stiffness_agent.dataset_registry import check_test_lock, validate_sample_artifacts
from stiffness_agent.matrix_validation import compare_matrices, read_square_matrix
from stiffness_agent.project_config import load_project_config


class StiffnessAgentCliTests(unittest.TestCase):
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
        development = parser.parse_args(["verify-dataset", "--development"])
        self.assertTrue(development.development)

        plan = parser.parse_args(["validate-data-plan", "plan.json"])
        self.assertEqual(plan.command, "validate-data-plan")

        register = parser.parse_args(
            ["register-sample", "--meta", "sample.json", "--split", "validation"]
        )
        self.assertEqual(register.split, "validation")

        lock = parser.parse_args(["check-test-lock"])
        self.assertEqual(lock.command, "check-test-lock")

        reset = parser.parse_args(["reset-plan", "--reason", "切换单元类型"])
        self.assertEqual(reset.reason, "切换单元类型")
        self.assertEqual(parser.parse_args(["replan"]).command, "replan")
        self.assertEqual(
            parser.parse_args(["validate-project"]).command, "validate-project"
        )

    def test_accepts_non_24_project_configuration(self) -> None:
        payload = {
            "schema_version": 1,
            "project_id": "quad-2d",
            "element_type": "CPS4",
            "matrix_dimensions": [8, 8],
            "node_count": 4,
            "dof_labels_per_node": ["u", "v"],
            "diagnostic_groups": {"translation": ["u", "v"]},
            "dataset": "data/datasets/cps4.json",
            "primary_sample": "data/cps4/metadata/sample.json",
            "adapter": {
                "kind": "command",
                "build_command": ["cmake", "--build", "build"],
                "evaluate_command": ["build/cps4", "{sample}"],
            },
            "agent": {
                "allowed_patch_paths": ["src/cps4.cpp"],
                "test_paths": [],
                "experiment_classes": ["formulation"],
            },
            "acceptance": {"target_error": 0.02},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            project = load_project_config(path)
        self.assertEqual(project.matrix_size, 8)
        self.assertEqual(project.dof_label(7), "n4.v")
        self.assertEqual(project.diagnostic_index_groups()["translation"], list(range(8)))

    def test_reads_and_compares_arbitrary_square_matrix_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerows([[2.0, 0.0], [0.0, 3.0]])
            matrix = read_square_matrix(path, 2)
        metrics = compare_matrices(matrix, [[2.0, 0.0], [0.0, 2.0]])
        self.assertGreater(metrics["frobenius_relative_error"], 0.0)
        self.assertEqual(metrics["max_absolute_error"], 1.0)

    def test_command_adapter_generates_generic_non_24_report(self) -> None:
        payload = {
            "schema_version": 1,
            "project_id": "matrix-2",
            "element_type": "TEST2",
            "matrix_dimensions": [2, 2],
            "node_count": 1,
            "dof_labels_per_node": ["u", "v"],
            "diagnostic_groups": {"all": ["u", "v"]},
            "dataset": "data/datasets/test2.json",
            "primary_sample": "data/test2/metadata/sample.json",
            "adapter": {
                "kind": "command",
                "evaluate_command": [sys.executable, "-c", "pass"],
            },
            "agent": {
                "allowed_patch_paths": ["src/test2.cpp"],
                "test_paths": [],
                "experiment_classes": ["formulation"],
            },
            "acceptance": {"target_error": 0.01},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_path = root / "project.json"
            project_path.write_text(json.dumps(payload), encoding="utf-8")
            reference = root / "reference.csv"
            actual = root / "actual.csv"
            for path, rows in (
                (reference, [[2.0, 0.0], [0.0, 2.0]]),
                (actual, [[2.0, 0.0], [0.0, 2.0]]),
            ):
                with path.open("w", newline="", encoding="utf-8") as handle:
                    csv.writer(handle).writerows(rows)
            sample = root / "sample.json"
            sample.write_text(
                json.dumps(
                    {
                        "sample_id": "sample-2",
                        "element_type": "TEST2",
                        "reference_matrix": str(reference),
                        "implementation_matrix": str(actual),
                    }
                ),
                encoding="utf-8",
            )
            project = load_project_config(project_path)
            code, runtime = prepare_adapter(project)
            report = root / "report.md"
            self.assertEqual(code, 0)
            self.assertEqual(evaluate_sample(project, runtime, sample, report), 0)
            report_text = report.read_text(encoding="utf-8")
        self.assertIn("matrix_dimensions: 2 x 2", report_text)
        self.assertIn("Frobenius relative error: 0.0", report_text)

    @patch("stiffness_agent.verification.run_checked", side_effect=[0, 0, 0, 0])
    def test_verification_driver_uses_four_direct_process_calls(self, mocked_run) -> None:
        self.assertEqual(run_verification(), 0)
        self.assertEqual(mocked_run.call_count, 4)
        commands = [call.args[0] for call in mocked_run.call_args_list]
        self.assertTrue(any("src/cli/s4_stiffness_cli.cpp" in command for command in commands))
        self.assertTrue(any("tests/s4_stiffness_tests.cpp" in command for command in commands))
        self.assertFalse(any(command and command[0] == "bash" for command in commands))

    @patch("stiffness_agent.api_check.call_openai_agent", return_value="API_OK")
    @patch("stiffness_agent.api_check.load_openai_config")
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
            Path("data/reference/abaqus/metadata/sample_001.json")
        )
        self.assertEqual(artifact["sample_id"], "sample_001")
        self.assertEqual(artifact["meta_relative"], "data/reference/abaqus/metadata/sample_001.json")
        passed, message = check_test_lock()
        self.assertFalse(passed)
        self.assertIn("为空", message)


if __name__ == "__main__":
    unittest.main()

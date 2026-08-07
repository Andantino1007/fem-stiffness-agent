#!/usr/bin/env python3
"""统一 Python CLI 与验证驱动的离线测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from shell_agent.api_check import perform_api_check
from shell_agent.cli import build_parser
from shell_agent.verification import run_verification


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


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""OpenAI 兼容客户端的离线单元测试，不发起网络请求。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from model_api_client import (
    OpenAIConfig,
    OpenAIHttpError,
    build_api_request,
    call_openai_agent,
    extract_chat_completions_text,
    extract_responses_text,
)


class OpenAIClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = OpenAIConfig(api_key="test-key", base_url="https://example.test/v1")

    def test_responses_request_uses_responses_endpoint_and_input(self) -> None:
        url, body = build_api_request("responses", self.config, "系统提示词", "用户提示词")
        self.assertEqual(url, "https://example.test/v1/responses")
        self.assertIn("input", body)
        self.assertNotIn("messages", body)
        self.assertEqual(body["max_output_tokens"], 1800)
        self.assertEqual(body["reasoning"], {"effort": "low"})

    def test_chat_completions_request_uses_messages(self) -> None:
        url, body = build_api_request("chat_completions", self.config, "系统提示词", "用户提示词")
        self.assertEqual(url, "https://example.test/v1/chat/completions")
        self.assertIn("messages", body)
        self.assertNotIn("input", body)
        self.assertEqual(body["max_tokens"], 1800)

    def test_extracts_text_from_both_response_shapes(self) -> None:
        self.assertEqual(extract_responses_text({"output_text": "结果 A"}), "结果 A")
        self.assertEqual(extract_chat_completions_text({"choices": [{"message": {"content": "结果 B"}}]}), "结果 B")

    def test_auto_mode_falls_back_to_chat_completions_after_responses_404(self) -> None:
        config = OpenAIConfig(api_key="test-key", base_url="https://example.test/v1", api_style="auto")
        chat_payload = {"choices": [{"message": {"content": "回退成功"}}]}
        with patch("model_api_client.post_json", side_effect=[OpenAIHttpError(404, "endpoint not found"), chat_payload]) as post:
            result = call_openai_agent("系统提示词", "用户提示词", config)

        self.assertEqual(result, "回退成功")
        self.assertEqual(post.call_count, 2)
        self.assertTrue(post.call_args_list[0].args[0].endswith("/responses"))
        self.assertTrue(post.call_args_list[1].args[0].endswith("/chat/completions"))


if __name__ == "__main__":
    unittest.main()

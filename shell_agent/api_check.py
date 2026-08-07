"""OpenAI 兼容 API 的最小在线连通性检查。"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agent_openai_client import call_openai_agent, load_openai_config


def perform_api_check() -> dict[str, Any]:
    """发起最小真实请求，验证密钥、模型、网关和接口格式。"""
    config = load_openai_config()
    started = time.monotonic()
    response = call_openai_agent(
        "你是 API 连通性检查器。只返回 API_OK。",
        "返回 API_OK，不要添加其他内容。",
        config,
    )
    elapsed = time.monotonic() - started
    if not response.strip():
        raise RuntimeError("API 返回了空文本")
    return {
        "status": "passed",
        "model": config.model,
        "base_url": config.base_url,
        "api_style": config.api_style,
        "elapsed_seconds": round(elapsed, 3),
        "response_preview": response.strip()[:120],
    }


def print_api_check(result: dict[str, Any]) -> None:
    print("OpenAI API check passed.")
    print(f"Model: {result['model']}")
    print(f"Base URL: {result['base_url']}")
    print(f"API style: {result['api_style']}")
    print(f"Elapsed: {result['elapsed_seconds']} s")
    print(f"Response: {result['response_preview']}")

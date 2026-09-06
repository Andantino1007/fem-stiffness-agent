#!/usr/bin/env python3
"""多智能体工作流使用的轻量 OpenAI 兼容接口客户端。

模块支持 Responses API 和 Chat Completions API，仅依赖 Python 标准库，
因此在 PC 或 Mac 上运行工作流前无需额外安装依赖。
"""

from __future__ import annotations

import json
import os
import re
import time
import http.client
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_BASE_URL = "https://api.abacloud.cn/v1"
DEFAULT_API_STYLE = "auto"
VALID_API_STYLES = {"auto", "responses", "chat_completions"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOTENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_style: str = DEFAULT_API_STYLE
    timeout_seconds: int = 90
    max_retries: int = 2
    max_output_tokens: int = 1800
    reasoning_effort: str = "low"


class OpenAIClientError(RuntimeError):
    pass


class OpenAIHttpError(OpenAIClientError):
    """保留 HTTP 状态码，便于兼容模式判断是否需要切换接口。"""

    def __init__(self, status_code: int, details: str) -> None:
        super().__init__(f"OpenAI API HTTP {status_code}: {sanitize_error(details)}")
        self.status_code = status_code


def load_project_dotenv() -> None:
    """读取项目 .env 文件中简单的 KEY=VALUE 配置。

    已存在的环境变量优先于 .env 配置，因而可在命令行临时覆盖配置，无需修改文件。
    """
    if not DOTENV_PATH.exists():
        return

    for raw_line in DOTENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_openai_config() -> OpenAIConfig:
    load_project_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise OpenAIClientError("OPENAI_API_KEY is not set")

    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/") or DEFAULT_BASE_URL
    api_style = os.getenv("OPENAI_API_STYLE", DEFAULT_API_STYLE).strip().lower() or DEFAULT_API_STYLE
    if api_style not in VALID_API_STYLES:
        valid = ", ".join(sorted(VALID_API_STYLES))
        raise OpenAIClientError(f"OPENAI_API_STYLE must be one of: {valid}")
    timeout = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "90"))
    max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
    max_output_tokens = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1800"))
    reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "low").strip() or "low"
    return OpenAIConfig(
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_style=api_style,
        timeout_seconds=timeout,
        max_retries=max_retries,
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
    )


def sanitize_error(text: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_\\-]{6,}", "sk-***", text)


def extract_responses_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"].strip()

    parts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def extract_chat_completions_text(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [item.get("text", "") for item in content if isinstance(item, dict) and isinstance(item.get("text"), str)]
        return "\n".join(parts).strip()
    return ""


def build_api_request(style: str, cfg: OpenAIConfig, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    """按目标接口格式构造 URL 和请求体。"""
    if style == "responses":
        return (
            f"{cfg.base_url}/responses",
            {
                "model": cfg.model,
                "max_output_tokens": cfg.max_output_tokens,
                "reasoning": {"effort": cfg.reasoning_effort},
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
    if style == "chat_completions":
        return (
            f"{cfg.base_url}/chat/completions",
            {
                "model": cfg.model,
                "max_tokens": cfg.max_output_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
    raise OpenAIClientError(f"Unsupported API style: {style}")


def post_json(url: str, body: dict, cfg: OpenAIConfig) -> dict:
    """向兼容网关发送请求，并对可重试网络错误进行有限重试。"""
    last_error: Exception | None = None
    for attempt in range(cfg.max_retries + 1):
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {cfg.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Kagent-FEM-Workflow/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=cfg.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            if exc.code < 500 or attempt >= cfg.max_retries:
                raise OpenAIHttpError(exc.code, details) from exc
            last_error = exc
        except (urllib.error.URLError, http.client.RemoteDisconnected, TimeoutError, ConnectionResetError) as exc:
            if attempt >= cfg.max_retries:
                raise OpenAIClientError(f"OpenAI API connection failed after {attempt + 1} attempt(s): {exc}") from exc
            last_error = exc
        time.sleep(1.5 * (attempt + 1))
    raise OpenAIClientError(f"OpenAI API request failed: {last_error}")


def call_openai_agent(system_prompt: str, user_prompt: str, config: OpenAIConfig | None = None) -> str:
    """调用已配置的接口；auto 模式在 Responses 接口 404 时切换到 Chat Completions。"""
    cfg = config or load_openai_config()
    styles = ["responses", "chat_completions"] if cfg.api_style == "auto" else [cfg.api_style]
    last_error: Exception | None = None

    for style in styles:
        url, body = build_api_request(style, cfg, system_prompt, user_prompt)
        try:
            payload = post_json(url, body, cfg)
        except OpenAIHttpError as exc:
            if cfg.api_style == "auto" and style == "responses" and exc.status_code == 404:
                last_error = exc
                continue
            raise
        text = extract_responses_text(payload) if style == "responses" else extract_chat_completions_text(payload)
        if text:
            return text
        raise OpenAIClientError(f"OpenAI API returned no response text from {style}")

    raise OpenAIClientError(f"OpenAI API request failed after API-style fallback: {last_error}")

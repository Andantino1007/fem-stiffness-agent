#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"
exec "$PYTHON_BIN" -m stiffness_agent verify --report docs/verification/样本001验证报告.md

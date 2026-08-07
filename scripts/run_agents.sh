#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ENGINE="langgraph"
ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --engine)
            if [[ $# -lt 2 ]]; then
                echo "--engine 需要 langgraph 或 legacy" >&2
                exit 64
            fi
            ENGINE="$2"
            shift 2
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
    PYTHON_BIN="${CONDA_PREFIX}/bin/python"
fi

case "$ENGINE" in
    langgraph)
        export LANGGRAPH_STRICT_MSGPACK="${LANGGRAPH_STRICT_MSGPACK:-true}"
        exec "$PYTHON_BIN" scripts/graph.py "${ARGS[@]}"
        ;;
    legacy)
        exec "$PYTHON_BIN" scripts/agents.py "${ARGS[@]}"
        ;;
    *)
        echo "未知 engine：$ENGINE；可选值为 langgraph、legacy" >&2
        exit 64
        ;;
esac

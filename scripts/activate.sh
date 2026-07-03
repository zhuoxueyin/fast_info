#!/usr/bin/env bash
# fastInfo · 激活虚拟环境(Linux/ECS 用)
# 用法: source scripts/activate.sh

VENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "✗ venv 不存在,请先建: python3.12 -m venv .venv --prompt fastinfo" >&2
    exit 1
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "✓ fastInfo venv activated"
echo "  Python: $(python --version 2>&1)"
echo "  PWD:    $(pwd)"
echo "  试试:   python fastinfo.py stats"
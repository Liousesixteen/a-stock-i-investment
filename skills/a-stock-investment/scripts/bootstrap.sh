#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

REPO_URL="${A_STOCK_INVESTMENT_REPO:-git@github.com:Liousesixteen/a-stock-i-investment.git}"
HTTPS_REPO_URL="${A_STOCK_INVESTMENT_HTTPS_REPO:-https://github.com/Liousesixteen/a-stock-i-investment.git}"

if [[ -n "${A_STOCK_INVESTMENT_HOME:-}" ]]; then
  PROJECT_DIR="$A_STOCK_INVESTMENT_HOME"
elif [[ -f "$REPO_ROOT/pyproject.toml" && -d "$REPO_ROOT/stock_assistant" ]]; then
  PROJECT_DIR="$REPO_ROOT"
else
  PROJECT_DIR="$HOME/.a-stock-investment"
fi

if [[ ! -f "$PROJECT_DIR/pyproject.toml" || ! -d "$PROJECT_DIR/stock_assistant" ]]; then
  mkdir -p "$(dirname "$PROJECT_DIR")"
  if ! git clone "$REPO_URL" "$PROJECT_DIR"; then
    rm -rf "$PROJECT_DIR"
    git clone "$HTTPS_REPO_URL" "$PROJECT_DIR"
  fi
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$PROJECT_DIR/.venv"
fi

"$PROJECT_DIR/.venv/bin/python" -m pip install --upgrade pip >/dev/null
"$PROJECT_DIR/.venv/bin/python" -m pip install -e "$PROJECT_DIR"

"$PROJECT_DIR/.venv/bin/stock-assistant" --help >/dev/null

cat <<EOF
A股投资分析决策 Skill 环境已就绪
PROJECT_DIR=$PROJECT_DIR
CLI=$PROJECT_DIR/.venv/bin/stock-assistant
EOF

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -n "${SC_WECHAT_PYTHON:-}" ]]; then
  PYTHON="$SC_WECHAT_PYTHON"
elif [[ -x "$SKILL_DIR/.venv/bin/python" ]]; then
  PYTHON="$SKILL_DIR/.venv/bin/python"
else
  PYTHON="python3"
fi

exec "$PYTHON" "$SCRIPT_DIR/publish_to_wechat.py" "$@"

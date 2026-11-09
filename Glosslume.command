#!/bin/bash
# Double-click to start Glosslume: runs the local server in this Terminal window and opens the reader in your browser.
# First run creates ./.venv and installs the app (needs internet once). Close the window or press Ctrl-C to stop.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"   # Terminal started from Finder has a short PATH

PORT=8780
URL="http://127.0.0.1:$PORT"

pause() { echo; read -r -n 1 -p "按任意键关闭 / Press any key to close…"; echo; }
fail() { echo "✗ $*"; pause; exit 1; }

# Already running? Just open it.
if curl -fs --max-time 2 "$URL/api/state" 2>/dev/null | grep -q '"version"'; then
  echo "Glosslume 已在运行，直接打开 / already running: $URL"
  open "$URL"
  exit 0
fi
if lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  fail "端口 $PORT 被别的程序占用了 / port $PORT is used by another program."
fi

# Python 3.11 or newer (the system python3 on macOS is older).
find_python() {
  local c p
  for c in python3.13 python3.12 python3.11 python3; do
    p=$(command -v "$c") || continue
    "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null && { echo "$p"; return 0; }
  done
  if command -v uv >/dev/null 2>&1; then uv python find '>=3.11' 2>/dev/null && return 0; fi
  return 1
}

if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  PY=$(find_python) || fail "找不到 Python 3.11 或更新版本 / Python 3.11+ not found. 安装 / install:  brew install python@3.12   或 / or   uv python install 3.12"
  echo "创建运行环境 / creating .venv with $PY"
  rm -rf .venv && "$PY" -m venv .venv || fail "创建虚拟环境失败 / could not create the virtual environment."
fi

# (Re)install when the project definition changed since the last install.
if [ ! -x .venv/bin/glosslume ] || [ pyproject.toml -nt .venv/.installed ]; then
  echo "安装依赖（首次需要联网）/ installing (internet needed the first time)…"
  .venv/bin/python -m pip install -q --disable-pip-version-check -e '.[all]' || fail "安装失败，请检查网络 / install failed, check your connection."
  touch .venv/.installed
fi

echo "启动 Glosslume / starting Glosslume at $URL"
.venv/bin/glosslume serve --port "$PORT" --open
status=$?
[ $status -ne 0 ] && { echo "服务退出，代码 / server exited with code $status"; pause; }
exit $status

#!/bin/bash
set -euo pipefail
umask 077
unset TZ
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -x "$ROOT/bin/codex-continue" ]]; then
  "$ROOT/install.sh"
fi
if [[ "${1:-}" == "--schedule-inspect" ]]; then
  exec /usr/bin/caffeinate -i python3 "$ROOT/schedule.py" --inspect
fi
if [[ $# -gt 0 ]]; then
  exec "$ROOT/bin/codex-continue" "$@"
fi
PYTHON="$(command -v python3)" || { echo '请安装 Xcode Command Line Tools（xcode-select --install）。'; exit 2; }
exec /usr/bin/caffeinate -i "$PYTHON" "$ROOT/schedule.py"

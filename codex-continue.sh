#!/bin/bash
set -euo pipefail
umask 077
unset TZ
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -r "$ROOT/scripts/runtime.sh" ]]; then
  echo "[未通过] 项目文件不完整，缺少 scripts/runtime.sh。请重新获取完整仓库：$ROOT"
  exit 2
fi
source "$ROOT/scripts/runtime.sh"
detect_mac
SCHEDULE=false
if [[ $# -eq 0 || "${1:-}" == --schedule-inspect || "${1:-}" == --preflight ]]; then
  SCHEDULE=true
  if [[ $# -gt 1 ]]; then
    echo '[未通过] 预约入口不接受额外参数。仅检查请用 --preflight；只读预约请用 --schedule-inspect。'
    exit 2
  fi
  printf '\nCodex 自动继续 · 启动检查\n[通过] 电脑：%s\n[通过] 系统：macOS %s\n' "$MACHINE_LABEL" "$MACOS_VERSION"
fi
if ! mkdir -p "$ROOT/logs"; then
  echo "[未通过] 无法创建日志目录：$ROOT/logs。请将项目放在你拥有写入权限的目录。" >&2
  exit 2
fi
if ! LOG_PROBE="$(mktemp "$ROOT/logs/.preflight.XXXXXX")"; then
  echo "[未通过] 日志目录不可写：$ROOT/logs。请检查目录的所有者和写入权限。" >&2
  exit 2
fi
rm -f "$LOG_PROBE"
PYTHON=''
if $SCHEDULE; then
  [[ -r "$ROOT/schedule.py" ]] || { echo '[未通过] 缺少 schedule.py，请重新获取完整项目后再预约。'; exit 2; }
  PYTHON="$(command -v python3)" || { echo '[未通过] 未找到 Python 3。请运行 xcode-select --install，安装完成后重试。'; exit 2; }
  if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 2)'; then
    echo "[未通过] Python 版本或运行环境不符合要求：$PYTHON。需要 Python 3.9 或更新版本，请安装后重试。"
    exit 2
  fi
  [[ -x /usr/bin/caffeinate ]] || { echo '[未通过] 缺少 macOS caffeinate，无法启用预约期间的防空闲睡眠。'; exit 2; }
  printf '[通过] Python：%s（%s）\n[通过] 预约防空闲睡眠工具、日志目录可用\n' "$("$PYTHON" --version 2>&1)" "$PYTHON"
fi
REBUILD=false
if [[ ! -x "$ROOT/bin/codex-continue" || "$ROOT/Sources/main.swift" -nt "$ROOT/bin/codex-continue" || "$ROOT/install.sh" -nt "$ROOT/bin/codex-continue" || "$ROOT/scripts/runtime.sh" -nt "$ROOT/bin/codex-continue" ]]; then
  REBUILD=true
elif ! /usr/bin/lipo "$ROOT/bin/codex-continue" -verify_arch "$NATIVE_ARCH" >/dev/null 2>&1; then
  REBUILD=true
fi
if $REBUILD; then
  echo "[检查] 需要构建或更新 $NATIVE_ARCH 辅助程序。"
  "$ROOT/install.sh"
fi
if ! /usr/bin/lipo "$ROOT/bin/codex-continue" -verify_arch "$NATIVE_ARCH" >/dev/null 2>&1 || ! /usr/bin/codesign --verify "$ROOT/bin/codex-continue"; then
  echo '[未通过] 辅助程序架构或签名校验失败。请执行项目中的 ./install.sh 重新构建，再从同一个终端重试。'
  exit 2
fi
if $SCHEDULE; then
  echo "[通过] 辅助程序：$NATIVE_ARCH 架构与本地签名校验通过"
  case "${1:-}" in
    --schedule-inspect) exec /usr/bin/caffeinate -di "$PYTHON" "$ROOT/schedule.py" --inspect ;;
    --preflight) exec "$PYTHON" "$ROOT/schedule.py" --preflight ;;
    '') exec /usr/bin/caffeinate -di "$PYTHON" "$ROOT/schedule.py" ;;
  esac
fi
exec /usr/bin/arch "-$NATIVE_ARCH" "$ROOT/bin/codex-continue" "$@"

#!/bin/bash
# 共用的 macOS 与真实芯片识别，供启动器和构建脚本使用。
detect_mac() {
  if [[ "$(uname -s)" != Darwin ]]; then
    echo '[未通过] 运行平台：本工具需要 macOS 14 或更新版本，不能在 Linux 或 Windows 上运行。' >&2
    return 2
  fi
  MACOS_VERSION="$(/usr/bin/sw_vers -productVersion)"
  local major="${MACOS_VERSION%%.*}"
  if [[ ! "$major" =~ ^[0-9]+$ ]] || (( major < 14 )); then
    echo "[未通过] 系统版本：当前 macOS $MACOS_VERSION，需要 macOS 14 或更新版本。请先升级系统。" >&2
    return 2
  fi
  local arm translated
  arm="$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null || true)"
  translated="$(/usr/sbin/sysctl -n sysctl.proc_translated 2>/dev/null || true)"
  classify_mac "$(uname -m)" "$arm" "$translated" || return $?
  export CODEX_CONTINUE_NATIVE_ARCH="$NATIVE_ARCH"
}

classify_mac() {
  local machine="$1" arm="$2" translated="$3"
  if [[ "$arm" == 1 || "$translated" == 1 || "$machine" == arm64 ]]; then
    NATIVE_ARCH=arm64
    MACHINE_LABEL='Apple Silicon（M 系列）'
    if [[ "$translated" == 1 ]]; then
      MACHINE_LABEL+='；当前终端经 Rosetta 运行，辅助程序将以 ARM64 原生运行'
    fi
  elif [[ "$machine" == x86_64 ]]; then
    NATIVE_ARCH=x86_64
    MACHINE_LABEL='Intel；辅助程序将以 x86_64 原生运行'
  else
    echo '[未通过] 无法识别芯片架构，请运行 uname -m 并附上输出报告问题。' >&2
    return 2
  fi
}

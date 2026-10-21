#!/bin/bash
set -euo pipefail
trap 'echo "[未通过] 构建未完成。请检查上方编译错误；如工具链未就绪，先运行 xcode-select --install。原有正式二进制不会被失败构建替换。" >&2' ERR
cd "$(dirname "$0")"
umask 077
source "./scripts/runtime.sh"
detect_mac
mkdir -p bin logs work
BUILD_DIR="$(mktemp -d "$PWD/work/build.XXXXXX")"
trap 'rm -rf -- "$BUILD_DIR"' EXIT
xcrun --find swiftc >/dev/null 2>&1 || { echo '[未通过] 未找到 Swift 编译器。请运行 xcode-select --install，完成安装后重新运行本命令。'; exit 2; }
if [[ "${1:-}" == "--universal" ]]; then
  xcrun swiftc -target x86_64-apple-macosx14.0 Sources/main.swift -o "$BUILD_DIR/codex-continue-x86_64"
  xcrun swiftc -target arm64-apple-macosx14.0 Sources/main.swift -o "$BUILD_DIR/codex-continue-arm64"
  xcrun lipo -create "$BUILD_DIR/codex-continue-x86_64" "$BUILD_DIR/codex-continue-arm64" -output "$BUILD_DIR/codex-continue"
else
  [[ $# -eq 0 ]] || { echo '用法：./install.sh [--universal]'; exit 2; }
  xcrun swiftc -target "${NATIVE_ARCH}-apple-macosx14.0" Sources/main.swift -o "$BUILD_DIR/codex-continue"
fi
/usr/bin/codesign --force --sign - --identifier local.codex-continue-automation "$BUILD_DIR/codex-continue"
chmod 700 "$BUILD_DIR/codex-continue"
mv "$BUILD_DIR/codex-continue" bin/codex-continue
printf '[通过] 构建完成（%s）；首次构建或更新后可能需要在辅助功能设置重新授权。\n' "$MACHINE_LABEL"
printf '程序：'
file bin/codex-continue

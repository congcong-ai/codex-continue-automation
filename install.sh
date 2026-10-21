#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
umask 077
mkdir -p bin logs work
xcrun --find swiftc >/dev/null || { echo '请先运行 xcode-select --install，安装完成后重试。'; exit 1; }
if [[ "${1:-}" == "--universal" ]]; then
  xcrun swiftc -target x86_64-apple-macosx14.0 Sources/main.swift -o work/codex-continue-x86_64
  xcrun swiftc -target arm64-apple-macosx14.0 Sources/main.swift -o work/codex-continue-arm64
  xcrun lipo -create work/codex-continue-x86_64 work/codex-continue-arm64 -output bin/codex-continue.new
else
  [[ $# -eq 0 ]] || { echo '用法：./install.sh [--universal]'; exit 2; }
  xcrun swiftc -target "$(uname -m)-apple-macosx14.0" Sources/main.swift -o bin/codex-continue.new
fi
/usr/bin/codesign --force --sign - --identifier local.codex-continue-automation bin/codex-continue.new
mv bin/codex-continue.new bin/codex-continue
chmod 700 bin/codex-continue
printf '安装完成：'
file bin/codex-continue

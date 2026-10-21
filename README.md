# Codex Continue Automation：macOS 上的 Codex 自动继续工具

[![许可证：MIT](https://img.shields.io/badge/许可证-MIT-green.svg)](LICENSE)
[![系统：macOS 14+](https://img.shields.io/badge/系统-macOS%2014%2B-blue.svg)](#环境要求)
[![实现：Swift 与 Python](https://img.shields.io/badge/实现-Swift%20%2B%20Python-orange.svg)](#项目结构)

**Codex Continue Automation 是一个开源的 macOS 桌面自动化工具，用于一次性定时或立即向 Codex 会话发送预先写好的「继续」。** 它通过 Swift 和原生辅助功能接口 AXUIElement 检查会话、草稿与发送按钮，使用 Python 标准库完成终端预约，无需第三方包。

适合希望在指定时间继续已有任务，或在一轮执行中继续多个指定置顶会话的用户。需要你提前在各目标会话输入 `继续`，工具不会代写提示词，也不会循环催促模型。

> 本项目是社区工具，与 OpenAI 无隶属关系。它操作本机桌面界面，不调用 Codex CLI 或 OpenAI API，不提供额度绕过、自动续费或后台无人值守保证。

## 导航

- [快速开始](#快速开始)
- [预约与命令](#预约与命令)
- [发送条件与防重复机制](#发送条件与防重复机制)
- [常见问题](#常见问题)
- [验证状态](docs/verification.md)
- [贡献指南](CONTRIBUTING.md)
- [GEO 与 SEO 说明](docs/discoverability.md)

## 能力一览

| 项目 | 当前行为 |
| --- | --- |
| 运行平台 | macOS 14 及更新版本 |
| 处理对象 | Bundle ID 为 `com.openai.codex` 的桌面应用 |
| 自动继续 | 仅发送首尾去空白后恰好为 `继续` 的现有草稿 |
| 单次预约 | 输入本地时间，终端等待后执行一次 |
| 批量继续 | 重复传入 `--pinned-title`，限定多个置顶会话 |
| 只读检查 | `--inspect` 不切换会话；`--test` 可切换但不发送 |
| 防重复 | 进程互斥锁；每个目标每轮最多尝试一次发送；结果不确定时不重发 |
| 安装方式 | 从源码本机构建，可构建 Intel / Apple Silicon 通用二进制 |
| 依赖 | Swift、macOS 系统框架、Python 3 标准库 |
| 开源协议 | MIT，允许商用、修改和分发，需保留版权及许可声明 |

## 环境要求

- macOS 14 或更新版本，已安装并登录目标桌面应用。
- Xcode Command Line Tools，提供 `swiftc`、`xcrun` 等构建工具。
- Python 3，可用 `python3 --version` 检查。
- 为实际启动工具的终端或宿主应用授予「辅助功能」权限。
- Mac 已登录、未锁屏，桌面可交互；Codex 侧边栏展开，目标聊天已保存、标题唯一。

缺少编译工具时，执行 `xcode-select --install`，完成系统安装后继续。

## 快速开始

### 1. 克隆并构建

```bash
git clone https://github.com/congcong-ai/codex-continue-automation.git
cd codex-continue-automation
./install.sh
```

默认生成当前机器架构的 `bin/codex-continue`。项目可放在任意目录，入口会相对自身定位源码和运行文件。

需要同时支持 Intel 和 Apple Silicon 时：

```bash
./install.sh --universal
file bin/codex-continue
```

换一台 Mac 后须重新授予权限；如系统阻止运行，可在目标机器从源码重新构建。

### 2. 授予权限并检查界面

在「系统设置 → 隐私与安全性 → 辅助功能」中，为实际启动工具的终端或宿主应用授权。系统也可能要求添加构建后的 `bin/codex-continue`。重新编译、移动文件或更换启动方式后，可能需要重新授权。

```bash
./codex-continue.sh --inspect
```

此命令只读取当前焦点窗口，不切换聊天、不发送消息。工具不使用模拟按键、坐标点击或屏幕录制。

### 3. 准备草稿并只读预检

在已保存且标题唯一的置顶会话中输入 `继续`，暂不发送。以下示例中的标题应替换为你的目标会话标题：

```bash
./codex-continue.sh --test --pinned-title '我的任务'
```

`--test` 允许切换会话检查草稿，**不会试发消息**。

### 4. 执行一次

确认预检通过后，可以立即向该目标发送：

```bash
./codex-continue.sh --run-now --pinned-title '我的任务'
```

执行后检查目标聊天历史。若日志为「结果不确定」，先人工核对，避免再次运行造成重复发送。

## 预约与命令

### 预约一次自动继续

```bash
./codex-continue.sh
```

按提示输入 `01:40` 或 `2026-10-22 01:40`，使用 Mac 的本地时区：

- 只填时分且今天已过该时刻时，明确提示按次日处理。
- 完整日期时间已过期时拒绝；夏令时不存在或重复的时刻也会拒绝。
- 关闭终端、进程退出或 `Ctrl+C` 会取消预约。
- `caffeinate -i` 尽量防止空闲睡眠；合盖、锁屏、退出登录仍可能导致 GUI 不可用。
- 延迟超过预约时间两分钟时取消，不补发。

**交互预约目前不支持限定会话标题，触发时使用默认目标规则。** 请预先检查置顶会话及草稿：可靠置顶列表中符合条件的会话会被逐个处理；列表无法可靠识别时，可能降级为当前活动会话。需要精确限定目标时，使用上述立即执行命令。

### 批量继续多个置顶会话

```bash
# 先只读检查两个指定目标。
./codex-continue.sh --test --pinned-title '任务甲' --pinned-title '任务乙'

# 确认后，在一轮执行中分别尝试发送一次。
./codex-continue.sh --run-now --pinned-title '任务甲' --pinned-title '任务乙'
```

重复标题会去重；任一指定目标不在可靠识别的置顶列表中时，整轮在发送前拒绝。限定目标模式不会降级到其它会话。

### 仅处理当前会话

目标可以不置顶，但必须是已保存、可在侧边栏唯一识别的会话，且标题精确匹配：

```bash
./codex-continue.sh --test --current-only --expect-title '独立测试会话'
./codex-continue.sh --run-now --current-only --expect-title '独立测试会话'
```

### 命令速查

| 命令或参数 | 行为 | 会发送吗 |
| --- | --- | --- |
| 无参数 | 交互预约一次默认目标执行 | 到时可能发送 |
| `--inspect` | 读取当前焦点窗口 | 否 |
| `--test` | 检查默认目标，可切换会话 | 否 |
| `--run-now` | 立即执行默认目标规则 | 是，满足条件时 |
| `--pinned-title '标题'` | 与 `--test` 或 `--run-now` 组合，可重复 | 由执行模式决定 |
| `--current-only --expect-title '标题'` | 与 `--test` 或 `--run-now` 组合，仅检查当前会话 | 由执行模式决定 |
| `--schedule-inspect` | 预约一次只读诊断，不切换会话 | 否 |
| `--self-test` | 运行内置识别回归测试 | 否 |

`--pinned-title` 与 `--current-only` 不可混用。`--run-now` 未限定标题时，会按默认规则处理所有可靠识别的置顶会话；可靠空列表不发送。

## 发送条件与防重复机制

工具在发送前重新读取界面，只有符合以下条件才尝试提交：

1. 目标应用、前台进程和焦点窗口能够确认；窗口、聊天工具栏和侧边栏身份一致。
2. 置顶分组与会话标题可可靠识别；重名、结构未知、加载未完成时按规则跳过或停止。
3. 主内容区域中只有一个带已知标签的消息输入框，其草稿去掉首尾空白后恰好为 `继续`。
4. 输入框和唯一发送按钮均启用，且没有停止、排队或处理中状态。
5. 系统处于已登录且未锁屏状态，提交前目标身份、草稿和焦点复核通过。

每个目标每轮最多执行一次 `AXPress`；失败或结果不确定时不重试，也没有回车和坐标点击回退。互斥锁防止多个本工具实例同时执行，但不能防止你在不同轮次手动重复运行。

成功判据是目标对话中新增一条正文恰好为 `继续` 的用户历史消息。`AXPress` 返回成功、输入框清空均不能单独证明提交成功；界面历史证据也不能独立证明服务器已接收。

## 常见问题

### 如何让 Codex 在指定时间自动继续？

提前在目标会话写入 `继续`，运行 `./codex-continue.sh` 输入未来时间，并保持终端与可交互桌面可用。当前提供一次性终端预约，没有每日重复任务或 launchd 后台配置。

### 是否支持 Windows、Linux、Codex CLI 或远程服务器？

当前实现依赖 macOS 的 Cocoa 和 AXUIElement，只面向本机桌面应用。它不执行 Codex CLI 业务任务，也不通过 API 提交提示词。

### 是否需要 API Key 或额外安装第三方包？

工具本身不需要 API Key、pip 包或 Swift 第三方包；目标桌面应用仍需正常登录并具备可用的模型访问权限。

### 为什么草稿里明明有「继续」，却没有发送？

草稿必须恰好为 `继续`，`继续吧` 等内容不会匹配。聊天历史里的「继续」不算草稿。按钮禁用、生成中、排队、重名会话、窗口焦点变化或 AX 结构无法确认时，也会跳过。

### 是否支持 M 系列 Mac？

安装脚本支持 ARM64 和通用构建。已有记录显示 ARM64 编译通过，Apple Silicon / M4 真机运行仍待验证；Intel 有历史真实发送记录。详见[验证状态](docs/verification.md)。

### 更新 Codex 后还能用吗？

当前适配器依赖可见标题和已知中英文辅助功能标签，没有使用应用内部会话 ID。界面更新可能导致识别失败。更新后先运行 `--inspect` 和限定目标的 `--test`。

### 日志会包含聊天内容吗？

运行日志写在本地 `logs/执行.jsonl`、`logs/预约.jsonl`，可能包含会话标题、状态和错误。`--inspect` 记录输入框标签、字符数及是否匹配，不输出完整草稿。开发探针 `Sources/Probe.swift` 会输出 AX 树，可能含聊天正文；分享前需脱敏。

`logs/`、备份、缓存和构建产物已由 `.gitignore` 排除。工具代码不主动上传诊断日志；实际发送后的消息由目标桌面应用按其自身方式处理。

### 提示没有权限、没有窗口或结果不确定，怎么办？

| 提示 | 处理方式 |
| --- | --- |
| 辅助功能权限缺失 | 为实际启动入口授权，必要时重新打开终端并运行 `--inspect` |
| 没有可操作窗口 | 打开应用主窗口并解锁桌面 |
| 当前活动会话无法可靠识别 | 展开侧边栏，确认标题唯一，关闭弹出菜单并等待加载完成 |
| 发送按钮不可用或排队 | 等待当前任务结束，检查界面中的额度或状态提示 |
| 结果不确定 | 先查看目标历史，确认是否新增消息，再决定后续操作 |

## 开发与验证

```bash
./install.sh
./codex-continue.sh --self-test
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

这些命令验证构建、识别逻辑和预约流程，不会真实发送消息。真实发送验收需要独立测试聊天、明确目标和人工核对，参见[验证状态与验收步骤](docs/verification.md)。

## 项目结构

```text
Sources/main.swift             原生会话识别、发送与内置回归测试
Sources/Probe.swift            开发用 AX 树探针
codex-continue.sh              命令入口与防空闲睡眠包装
install.sh                     本机构建、通用构建与临时签名
schedule.py                    本地时区一次性预约
tests/test_schedule.py         时间解析与预约执行边界测试
tests/真实AX消息历史.json        最小测试对话的 AX 回放样本
docs/                          验证状态与检索说明
```

## 开源与贡献

欢迎通过 [Issues](https://github.com/congcong-ai/codex-continue-automation/issues) 报告问题或提出建议，提交代码前请阅读[贡献指南](CONTRIBUTING.md)。报告时请提供系统、架构、复现命令和脱敏输出。

项目采用 [MIT 许可证](LICENSE)。允许使用、复制、修改、合并、发布、分发、再许可及销售软件副本，但须保留版权和许可声明；软件按现状提供，不附带担保。

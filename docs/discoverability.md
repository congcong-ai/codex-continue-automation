# GEO 与 SEO：项目发现与引用

Codex Continue Automation 的公开信息入口是 [GitHub 仓库](https://github.com/congcong-ai/codex-continue-automation) 和根目录 README。项目面向需要 macOS Codex 自动继续、一次性定时发送和置顶会话批量继续的用户。

## 已落实的内容优化

- README 标题包含项目名、平台和用途；开头直接解释工具行为、实现与适用对象。
- 用能力表、命令表和常见问题回答安装、预约、批量、权限、平台、API Key、隐私及失败处理问题。
- 安装命令、项目结构和内部文档均使用可解析文本，方便直接阅读与检索引用。
- 验证状态独立维护，区分真实运行、编译通过与尚待验证的能力。
- 根目录 `llms.txt` 提供项目事实摘要与主要文档链接，供愿意读取它的工具参考。

`llms.txt` 只是额外的文档入口，不是搜索收录或 AI 引用的保证，也不是 Google 要求的优化文件。GitHub README 的 HTML 元数据与抓取规则由 GitHub 控制，仓库内添加网页 meta、robots.txt 或 sitemap.xml 无法修改 GitHub 仓库页面的行为。

## 仓库简介与主题建议

以下内容供仓库维护者手动设置，本次代码提交不会修改 GitHub 仓库设置。

建议简介：

> macOS 上的 Codex 自动继续工具：一次性定时发送「继续」，支持指定置顶会话批量处理，Swift 原生辅助功能与 Python 标准库实现。

建议主题：`codex`、`codex-automation`、`macos`、`swift`、`python`、`accessibility`、`desktop-automation`、`task-scheduling`。

## 维护原则

功能变化时同步更新 README、验证状态与 `llms.txt`。使用真实命令与证据描述项目，不堆砌关键词，不编造评价、用户数、性能数据或兼容性。

Google 的[生成式 AI 搜索优化指南](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)强调有用的原创内容、清晰结构与基础 SEO；遵循指南不保证抓取、收录、排名或引用。当前交付的是仓库文档优化，尚无搜索收录或 AI 引用效果的测量结果。

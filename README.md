# XQAgent 🎻

轻量 AI Agent，纯 Python 标准库实现。运行于 macOS，提供原生 .app 桌面体验。

> **开箱即用** — 内置 Python 3.11 运行环境，无需安装任何依赖。

## 快速开始

### 1. 安装 LM Studio

下载 [LM Studio](https://lmstudio.ai/)，加载一个模型（推荐 `qwen/qwen3.5-9b`），启动本地服务器（默认端口 1234）。

### 2. 下载 XQAgent

从 [Releases](../../releases) 下载最新版 `XQAgent-v1.0.0.zip`：

```bash
unzip XQAgent-v*.zip
cd XQAgent
bash install.sh    # 安装到 /Applications/
```

### 3. 启动

打开 `/Applications/XQAgent.app`。

> **macOS 15+ 首次打开**: 因 ad-hoc 签名，系统会提示未验证。
> 方法 A: 右键 → 打开（选择「打开」）
> 方法 B: 系统设置 → 隐私与安全性 →「仍要打开」

之后直接在对话界面聊天即可。也可在浏览器访问 `http://localhost:18777`。

## 功能

| 功能 | 说明 |
|------|------|
| **AI 对话** | SSE 流式响应，支持多轮对话和工具调用 |
| **文件操作** | 读写文件、搜索文件、列出目录 |
| **Shell 命令** | 执行 Shell 命令（带安全黑名单） |
| **网页抓取** | 获取网页内容并自动提取正文 |
| **天气查询** | 全球城市天气查询（无需 API Key） |
| **技能系统** | SKILL.md 格式，按需加载，20+ 内置技能 |
| **记忆系统** | L1 索引 → L2 事实 → L3 记录 → L4 会话摘要 |
| **AI 人设** | 自定义 AI 名称、性格，跨会话持久化 |
| **多模型配置** | 管理多个模型配置，随时切换默认模型 |
| **会话管理** | 新建、重命名、删除、切换对话 |
| **文件上传** | 通过原生 macOS 文件选择器上传文本/二进制文件 |
| **暗色主题** | 亮/暗主题切换 |
| **远控通道** | 支持微信、QQ、飞书等 7 个消息平台的桥接 |
| **macOS 原生** | Swift + WKWebView 壳，31MB 自包含 .app |

## 架构

```
XQAgent.app/
├── Contents/
│   ├── MacOS/XQAgent         ← Swift 原生壳
│   ├── Frameworks/           ← （可选）嵌入的依赖
│   └── Resources/
│       ├── python/           ← Python 3.11 运行环境 (25MB)
│       ├── app.py            ← HTTP 服务器 + 路由
│       ├── xq_agent.py       ← Agent 核心循环 (LLM+Function Calling)
│       ├── tools.py          ← 7 个内置工具
│       ├── skill_loader.py   ← SKILL.md 技能加载器
│       ├── memory/           ← L1-L4 多层记忆系统
│       ├── web/index.html    ← 单页 Web UI
│       ├── bridges/          ← 远控通道
│       ├── skills/           ← 已安装的技能
│       ├── sessions/         ← 运行时：会话数据
│       └── config.json       ← 运行时：模型配置
```

## 开发

### 环境要求

- macOS 12.0+
- Xcode Command Line Tools（编译 Swift 壳用）
- Python 3.11（构建时自动打包进 .app）

### 本地开发

```bash
# 1. 直接启动后端（在浏览器中调试）
python3 app.py --port 18777

# 2. 构建 macOS .app
bash mac/build.sh       # 构建到 XQAgent.app/
bash mac/distribute.sh  # 打包为分发包 dist/XQAgent-v*.zip
```

### 技能开发

技能是 `SKILL.md` 格式的 Markdown 文件，放在 `skills/` 目录下：

```yaml
---
name: my-skill
description: 技能描述
---

# 技能正文
（Markdown 指令，AI 按需加载后执行）
```

通过 Web UI 的「技能管理」页面安装/卸载。

## 安全

- 服务器仅监听 `127.0.0.1`，不暴露到局域网
- Shell 命令执行有内置黑名单防护
- 文件路径有系统目录保护（/etc、/var 等）
- 详细信息见 [SECURITY.md](SECURITY.md)

## 技术栈

```
后端: Python 3.11 (纯标准库, 零第三方依赖)
前端: 单页 HTML (Tailwind CSS + marked + highlight.js)
壳:   Swift 5 (Cocoa + WebKit)
API:  OpenAI 兼容格式 (兼容 LM Studio / Ollama / vLLM)
```

## 许可证

[MIT](LICENSE)

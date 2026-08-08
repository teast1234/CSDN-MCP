# 📝 csdn-blog-mcp — CSDN 博文自动写作与发布 MCP

**语言 / Languages:** **简体中文** | [English](./README.en.md)

一个 MCP（Model Context Protocol）服务器，让 AI Agent（Cursor、Claude 等）成为 CSDN 博客的**写作 + 发布助手**——生成 SEO 优化的博文骨架、打包保存草稿、SEO 自检、再通过浏览器自动化一键推送到 CSDN 草稿箱。它还能从你已发布的博文里提炼写作风格，让 AI 按你的语气写。

基于 [FastMCP](https://github.com/jlowin/fastmcp) 构建，发布走 Playwright 浏览器自动化路线，跨平台支持 Windows / macOS / Linux。

> ⭐ **如果这个项目帮到你，欢迎去仓库点个 Star 支持一下～**
> 👉 https://gitee.com/gdouage/csdn-mcp
> 你的一颗星，是个人开发者继续更新的最大动力 ❤️

| | |
|---|---|
| 仓库 | [gitee.com/gdouage/csdn-mcp](https://gitee.com/gdouage/csdn-mcp) |
| 协议 | [MIT](./LICENSE) |
| 作者 | abbuibuibui |
| 联系 | [3244940576@qq.com](mailto:3244940576@qq.com) |

> ⚠️ **重要风险提示**
> CSDN 没有公开的博文发布 API，本工具通过浏览器自动化模拟人工操作发布。
> - CSDN 用户协议禁止「使用未经授权的自动化程序发布内容」，请知悉风险。
> - 内置频率限制（默认每天 2 篇、间隔 ≥ 30 分钟）以降低封号风险。
> - 登录/发布可能触发验证码，需人工介入。
> - CSDN 编辑器改版会导致选择器失效，失败时会自动截图存证。

---

## 📌 项目介绍

| 能力 | 说明 |
|------|------|
| 写博文 | 生成 SEO 优化的 markdown 骨架（6 种风格预设），打包正文 + front-matter 保存为草稿 |
| 风格对齐 | 从你已发布的博文提炼写作风格，AI 按你的语气写（不套个人化称呼） |
| SEO 自检 | 标题长度/关键词前置、摘要、关键词密度、H2/H3 层级、代码块语言、图片 alt、标签数，0-100 评分 |
| 草稿管理 | 列出 / 读取 / 删除本地草稿，统一存放在 drafts/ |
| 发布 CSDN | Playwright 自动化打开编辑器、填标题、粘正文、选标签/分类/可见性、点发布、读回文章 URL |
| 登录管理 | 首次可见浏览器登录保存 session，之后 headless 发布；可检查/清除登录态 |
| 文章统计 | 通过 CSDN 公开接口读取阅读/点赞/评论/收藏数（无需登录） |
| 频率限制 | 内置每天发文上限 + 最小间隔，可查询当前状态 |

**核心流程：**

```text
get_style_guide → generate_blog_scaffold → 填充正文 → write_blog → seo_check → csdn_login(首次) → publish_csdn → csdn_stats
```

---

## 🏗️ 项目架构

```text
┌──────────────────────────────────────────────┐
│              AI Agent (Cursor / Claude)        │
│                  通过 MCP 协议调用               │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│            csdn-blog-mcp Server               │
│              (FastMCP, 14 个工具)              │
├──────────┬──────────┬──────────┬──────────────┤
│  写博文   │  草稿库   │  发布登录  │   统计/限流    │
│ (4 tools)│ (3 tools)│ (5 tools)│  (2 tools)  │
├──────────┴──────────┴──────────┴──────────────┤
│                  底层能力                       │
│  Markdown 解析 │ YAML front-matter │ Playwright │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│         CSDN 网页编辑器 / 公开统计 API           │
└──────────────────────────────────────────────┘
```

**目录结构：**

```text
csdn-blog-mcp/
├── src/csdn_blog_mcp/
│   ├── server.py          # MCP 服务入口 + 工具注册
│   ├── writer.py          # 写博文：generate_blog_scaffold / write_blog
│   ├── seo.py             # SEO 自检：seo_check
│   ├── library.py         # 草稿库：list / read / delete
│   ├── auth.py            # 登录态：check_login / login / clear_session
│   ├── publisher.py       # 发布：publish_csdn（Playwright 方案 A）
│   ├── stats.py           # 统计：csdn_stats（公开 API）
│   ├── style.py           # 风格指南加载：get_style_guide
│   ├── util.py            # run_in_thread：让浏览器工具绕开 MCP 的 asyncio 循环
│   └── config.py          # 路径 / cookie 存储 / 频率限制
├── STYLE_GUIDE.md         # 从作者博文提炼的写作风格提示词（MCP 自用）
├── drafts/                # 本地草稿存放处（git 忽略）
├── pyproject.toml
├── .gitignore
├── README.md             # 中文（默认，Gitee 首页展示）
└── README.en.md           # English
```

---

## 🛠️ 技术栈与依赖

| 层级 | 技术 |
|------|------|
| 协议 | MCP (Model Context Protocol) |
| 框架 | FastMCP |
| 语言 | Python 3.12+ |
| 浏览器自动化 | Playwright (Chromium) |
| HTTP 请求 | httpx（统计接口） |
| 构建系统 | setuptools |

---

## 🚀 快速开始

### 1. 环境要求

- Python **3.12+**
- 支持 MCP 的 AI 客户端（Cursor、Claude Desktop 等）
- 发布功能需安装 Playwright 浏览器内核（见下）

### 2. 获取代码

```bash
git clone https://gitee.com/gdouage/csdn-mcp.git
cd csdn-mcp
```

### 3. 安装

```bash
# 创建虚拟环境
python -m venv .venv

# Windows
.venv\Scripts\pip install -e .
.venv\Scripts\playwright install chromium

# macOS / Linux
.venv/bin/pip install -e .
.venv/bin/playwright install chromium
```

> `playwright install chromium` 会把浏览器内核下到本机缓存目录（Windows 是 `%LOCALAPPDATA%\ms-playwright`，macOS/Linux 是 `~/.cache/ms-playwright`），**不在项目里**，跨平台自动适配。

### 4. 配置 MCP 客户端

#### Cursor

添加到 `~/.cursor/mcp.json`（把 `<项目路径>` 换成你本机的实际路径）：

```json
{
  "mcpServers": {
    "csdn-blog-mcp": {
      "command": "<项目路径>/.venv/Scripts/python.exe",
      "args": ["-m", "csdn_blog_mcp.server"],
      "env": {
        "PYTHONPATH": "<项目路径>/src"
      }
    }
  }
}
```

> macOS / Linux 把 `Scripts/python.exe` 换成 `bin/python`。
> 可选环境变量 `CSDN_BLOG_HOME`：自定义草稿/cookie 存放目录（默认项目根目录）。

### 5. 首次登录 CSDN 🎬

让 AI 调用 `csdn_login`，会弹出一个浏览器，手动登录 CSDN（首次必须可见，可能遇验证码）。登录成功后 session 自动保存，之后发布就能 headless 跑。重启 Cursor，MCP 服务自动启动。

---

## 📡 14 个工具一览

### 写博文（4 个）

| 工具 | 功能 |
|------|------|
| `get_style_guide` | 返回从作者已发布博文提炼的写作风格提示词（语气、两种文章类型、标题/开头/结构/必备元素/SEO），写文前先调它对齐风格 |
| `generate_blog_scaffold` | 生成 SEO 优化的 markdown 骨架（6 种风格：开源项目介绍/保姆级教程/技术教程/原理分析/踩坑笔记/通用） |
| `write_blog` | 打包正文 + YAML front-matter，保存为本地草稿 |
| `seo_check` | 分析草稿 SEO，返回 0-100 评分 + 改进建议 |

### 草稿库（3 个）

| 工具 | 功能 |
|------|------|
| `list_drafts` | 列出本地草稿（按时间倒序） |
| `read_draft` | 读取草稿内容 + 元数据 |
| `delete_draft` | 删除草稿 |

### 发布与登录（5 个）

| 工具 | 功能 |
|------|------|
| `check_csdn_login` | 用已保存 session 检查是否仍登录 |
| `csdn_login` | 打开可见浏览器手动登录，保存 session |
| `clear_csdn_session` | 清除已保存 session |
| `publish_csdn` | 浏览器自动化把草稿发到 CSDN：**默认存草稿箱**（不公开），`as_draft=False` 时直接发布 |
| `diagnose_editor` | 探测 CSDN 编辑器各关键元素，报告每个选择器是否命中——`publish_csdn` 失败时跑它定位是哪个选择器被改版了 |

### 统计与限流（2 个）

| 工具 | 功能 |
|------|------|
| `csdn_stats` | 读取已发布文章的阅读/点赞/评论/收藏数（公开 API） |
| `rate_limit_status` | 查询当前发文频率限制状态 |

---

## 📝 典型工作流

### 场景 1：从零写一篇并发布

```text
get_style_guide()                  # 先读风格提示词，对齐作者语气/结构
generate_blog_scaffold("Playwright 自动化", ["playwright","python","爬虫"], "tutorial")
  → 拿到骨架，AI 按风格指南填充正文
write_blog(topic="Playwright 自动化完全指南", content=<填充后的正文>, tags=[...])
  → 保存草稿，拿到 file_path
seo_check(file_path)
  → 看评分，按建议修改
csdn_login()                      # 首次登录（会弹浏览器，手动登录）
publish_csdn(file_path)           # 默认存入 CSDN 草稿箱（不公开）
# 审阅满意后，在 CSDN 后台手动点发布；或 publish_csdn(file_path, as_draft=False) 直接发
csdn_stats(article_url)           # 直接发布后看数据
```

### 场景 2：只写不发（零风险）

```text
get_style_guide → generate_blog_scaffold → 填充 → write_blog → seo_check
# 草稿留在 drafts/，手动复制到 CSDN 编辑器发布（5 秒的事）
```

### 场景 3：发布前检查登录与限流

```text
rate_limit_status()       # 今天还能发吗？
check_csdn_login()         # session 还有效吗？
publish_csdn(file_path)   # 都 OK 再发
```

---

## 💡 设计说明

- **写作零风险**：`get_style_guide` / `generate_blog_scaffold` / `write_blog` / `seo_check` 纯本地文本处理，不碰网络
- **风格对齐**：从作者已发布博文提炼写作风格，但**不套个人化称呼**（如"小b"），保持中性语气
- **发布走方案 A**：Playwright 模拟人工操作 CSDN 网页编辑器，不碰内部 API，封号风险最低
- **默认存草稿箱**：`publish_csdn` 默认 `as_draft=True`，只存到 CSDN 在线草稿箱不公开，你审阅后再手动发布
- **session 持久化**：登录态存为 Playwright 标准 storageState JSON，git 忽略，过期提示重登
- **频率限制**：仅对**直接发布**生效（默认每天 2 篇、间隔 ≥ 30 分钟）；存草稿箱不限频
- **失败存证**：发布失败自动截图到 `.cookies/screenshots/`，方便排查选择器失效
- **选择器集中**：`publisher.py` 顶部 `SELECTORS` 字典统一管理，关键元素配多组回退选择器，CSDN 改版只需改这里
- **抗 UI 漂移**：固定视口 + 网络层广告拦截 + 弹层自动关闭 + 多选择器回退 + 鲁棒点击重试，缓解分辨率变化/广告/小改版导致的失效
- **自诊断**：`diagnose_editor` 探测编辑器各元素命中情况，`publish_csdn` 失败时跑它定位是哪个选择器被改版了
- **绕开 asyncio 循环**：MCP 服务在 asyncio 事件循环里跑工具函数，而 Playwright 的 sync API 拒绝在运行中的循环里启动；`util.run_in_thread` 装饰器检测到循环时把浏览器工具丢到独立线程执行，无循环时（独立脚本）直接跑，零开销
- **拟人节奏**：每步操作间随机延迟 0.8-2.2 秒，降低风控触发概率

---

## ⚠️ 风险与合规

| 风险 | 说明 | 应对 |
|------|------|------|
| 封号 | CSDN 对批量发文有风控 | 默认每天 2 篇、间隔 30 分钟、内容差异化 |
| 验证码 | 登录/发布可能弹滑块验证码 | 自动化过不了，需人工介入（csdn_login 弹浏览器） |
| ToS | 协议禁止未授权自动化发布 | 方案 A 风险最低；默认只存草稿箱 |
| UI 漂移 | CSDN 编辑器改版 | 多选择器回退 + 失败截图存证 + `diagnose_editor` 自诊断 |

**最务实路径**：先只用「写博文」部分（零风险），发布那一下保留人工点击。稳定运行后再开自动发布。

---

## 💬 反馈与贡献

如果这个项目对你有帮助，拜托：

1. ⭐ 去仓库点个 **Star**：[csdn-mcp](https://gitee.com/gdouage/csdn-mcp)
2. 🐛 遇到问题提 [Issue](https://gitee.com/gdouage/csdn-mcp/issues)
3. ✉️ 想交流可发邮件：[3244940576@qq.com](mailto:3244940576@qq.com)（作者：abbuibuibui）

也欢迎提交 Pull Request（请先说明改动目的与测试方式）～

---

## 📄 许可证

本项目基于 [MIT License](./LICENSE) 开源。

```text
Copyright (c) 2026 abbuibuibui
```

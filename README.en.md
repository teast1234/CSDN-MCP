# 📝 csdn-blog-mcp — CSDN Blog Auto-Writing & Publishing MCP

**Language / Languages:** [简体中文](./README.md) | **English**

An MCP (Model Context Protocol) server that turns AI agents (Cursor, Claude, etc.) into a **writing + publishing assistant** for CSDN blogs — generate SEO-optimized scaffolds, package drafts, run SEO checks, then push to the CSDN draft box via browser automation. It can also distill your writing style from your existing posts so the AI writes in your voice.

Built on [FastMCP](https://github.com/jlowin/fastmcp), publishing uses Playwright browser automation, cross-platform on Windows / macOS / Linux.

> ⭐ **If this project helps you, a Star on the repo is greatly appreciated~**
> 👉 https://gitee.com/gdouage/csdn-mcp
> Your star is the biggest motivation for a solo developer to keep updating ❤️

| | |
|---|---|
| Repo | [gitee.com/gdouage/csdn-mcp](https://gitee.com/gdouage/csdn-mcp) |
| License | [MIT](./LICENSE) |
| Author | abbuibuibui |
| Contact | [3244940576@qq.com](mailto:3244940576@qq.com) |

> ⚠️ **Important risk notice**
> CSDN has no public API for publishing; this tool drives the web editor via browser automation.
> - CSDN's ToS prohibits "unauthorized automated publishing" — be aware of the risk.
> - A built-in rate limit (default 2/day, ≥ 30 min apart) reduces ban risk.
> - Login/publish may trigger a captcha that needs manual handling.
> - CSDN editor UI changes can break selectors; a screenshot is saved on failure.

---

## 📌 Overview

| Capability | Description |
|------|------|
| Write | Generate SEO-optimized markdown scaffolds (6 style presets), package body + front-matter as a draft |
| Style alignment | Distill your writing style from your published posts; the AI writes in your tone (no personal persona) |
| SEO check | Title length/keyword-fronting, summary, keyword density, H2/H3 hierarchy, code-block language, image alt, tag count, 0-100 score |
| Draft library | List / read / delete local drafts, stored under drafts/ |
| Publish to CSDN | Playwright automation: open editor, fill title, paste body, set tags/category/visibility, click publish, read back article URL |
| Login management | First login in a visible browser saves the session; later runs are headless; check/clear session |
| Article stats | Read view/like/comment/collect counts via CSDN's public API (no login) |
| Rate limiting | Built-in daily cap + min interval; query current status |

**Core flow:**

```text
get_style_guide → generate_blog_scaffold → fill body → write_blog → seo_check → csdn_login(first time) → publish_csdn → csdn_stats
```

---

## 🏗️ Architecture

```text
┌──────────────────────────────────────────────┐
│              AI Agent (Cursor / Claude)        │
│                  via MCP protocol               │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│            csdn-blog-mcp Server               │
│              (FastMCP, 14 tools)               │
├──────────┬──────────┬──────────┬──────────────┤
│  Write   │  Drafts  │ Publish/ │   Stats/     │
│          │          │  Login   │   RateLimit  │
│ (4 tools)│ (3 tools)│ (5 tools)│  (2 tools)  │
├──────────┴──────────┴──────────┴──────────────┤
│                  Core layer                     │
│  Markdown parsing │ YAML front-matter │ Playwright │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│         CSDN web editor / public stats API     │
└──────────────────────────────────────────────┘
```

**Directory structure:**

```text
csdn-blog-mcp/
├── src/csdn_blog_mcp/
│   ├── server.py          # MCP entry + tool registration
│   ├── writer.py          # generate_blog_scaffold / write_blog
│   ├── seo.py             # seo_check
│   ├── library.py         # list / read / delete drafts
│   ├── auth.py            # check_login / login / clear_session
│   ├── publisher.py       # publish_csdn (Playwright, Plan A)
│   ├── stats.py           # csdn_stats (public API)
│   ├── style.py           # get_style_guide loader
│   ├── util.py            # run_in_thread: run browser tools off the MCP asyncio loop
│   └── config.py          # paths / cookie store / rate limit
├── STYLE_GUIDE.md         # Writing-style prompt distilled from the author's posts
├── drafts/                # Local drafts (git-ignored)
├── pyproject.toml
├── .gitignore
├── README.md             # Chinese (default, shown on Gitee homepage)
└── README.en.md           # English
```

---

## 🛠️ Tech stack

| Layer | Tech |
|------|------|
| Protocol | MCP (Model Context Protocol) |
| Framework | FastMCP |
| Language | Python 3.12+ |
| Browser automation | Playwright (Chromium) |
| HTTP | httpx (stats endpoint) |
| Build | setuptools |

---

## 🚀 Quick start

### 1. Requirements

- Python **3.12+**
- An MCP-capable AI client (Cursor, Claude Desktop, etc.)
- Playwright browser core for publishing (see below)

### 2. Get the code

```bash
git clone https://gitee.com/gdouage/csdn-mcp.git
cd csdn-mcp
```

### 3. Install

```bash
# Create a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\pip install -e .
.venv\Scripts\playwright install chromium

# macOS / Linux
.venv/bin/pip install -e .
.venv/bin/playwright install chromium
```

> `playwright install chromium` downloads the browser core to a machine-local cache (Windows: `%LOCALAPPDATA%\ms-playwright`, macOS/Linux: `~/.cache/ms-playwright`) — **not inside the project**, auto-adapted per platform.

### 4. Configure your MCP client

#### Cursor

Add to `~/.cursor/mcp.json` (replace `<project-path>` with your local path):

```json
{
  "mcpServers": {
    "csdn-blog-mcp": {
      "command": "<project-path>/.venv/Scripts/python.exe",
      "args": ["-m", "csdn_blog_mcp.server"],
      "env": {
        "PYTHONPATH": "<project-path>/src"
      }
    }
  }
}
```

> On macOS / Linux use `bin/python` instead of `Scripts/python.exe`.
> Optional env var `CSDN_BLOG_HOME`: custom directory for drafts/cookies (defaults to project root).

### 5. First login to CSDN 🎬

Ask the AI to call `csdn_login`; a browser opens for manual CSDN login (first login must be visible — a captcha may appear). After login the session is saved automatically and later publishing runs headless. Restart Cursor and the MCP service starts.

---

## 📡 The 14 tools

### Writing (4)

| Tool | Purpose |
|------|------|
| `get_style_guide` | Returns the writing-style prompt distilled from the author's posts (tone, two article types, title/opening/structure/required elements/SEO); call it first to align style |
| `generate_blog_scaffold` | Generate an SEO-optimized markdown scaffold (6 styles: project intro / step-by-step tutorial / technical / analysis / bug-notes / general) |
| `write_blog` | Package body + YAML front-matter, save as a local draft |
| `seo_check` | Analyze a draft's SEO, return a 0-100 score + suggestions |

### Draft library (3)

| Tool | Purpose |
|------|------|
| `list_drafts` | List local drafts (newest first) |
| `read_draft` | Read a draft's content + metadata |
| `delete_draft` | Delete a draft |

### Publishing & login (5)

| Tool | Purpose |
|------|------|
| `check_csdn_login` | Check whether the saved session is still logged in |
| `csdn_login` | Open a visible browser to log in manually, save the session |
| `clear_csdn_session` | Clear the saved session |
| `publish_csdn` | Browser automation to send a draft to CSDN: **default saves to draft box** (not public); `as_draft=False` publishes directly |
| `diagnose_editor` | Probe every key element of the CSDN editor and report which selector matched — run it when `publish_csdn` fails to find which selector CSDN changed |

### Stats & rate limit (2)

| Tool | Purpose |
|------|------|
| `csdn_stats` | Read view/like/comment/collect counts of a published article (public API) |
| `rate_limit_status` | Query the current publish rate-limit status |

---

## 📝 Typical workflows

### Scenario 1: write from scratch and publish

```text
get_style_guide()                  # read the style prompt first
generate_blog_scaffold("Playwright automation", ["playwright","python","crawler"], "tutorial")
  → get the scaffold, AI fills the body per the style guide
write_blog(topic="Playwright automation guide", content=<filled body>, tags=[...])
  → save draft, get file_path
seo_check(file_path)
  → check the score, fix per suggestions
csdn_login()                      # first login (opens a browser, log in manually)
publish_csdn(file_path)           # default: save to CSDN draft box (not public)
# review in CSDN, then publish manually; or publish_csdn(file_path, as_draft=False)
csdn_stats(article_url)           # check stats after direct publish
```

### Scenario 2: write only, no publish (zero risk)

```text
get_style_guide → generate_blog_scaffold → fill → write_blog → seo_check
# draft stays in drafts/, copy to the CSDN editor manually (5 seconds)
```

### Scenario 3: check login & rate limit before publishing

```text
rate_limit_status()       # can I still publish today?
check_csdn_login()         # is the session still valid?
publish_csdn(file_path)   # publish once both are OK
```

---

## 💡 Design notes

- **Writing is zero-risk**: `get_style_guide` / `generate_blog_scaffold` / `write_blog` / `seo_check` are pure local text processing, no network
- **Style alignment**: distills the author's writing style but **does not inject a personal persona** (e.g. "小b"), keeping a neutral tone
- **Plan A publishing**: Playwright simulates manual operation of the CSDN web editor, no internal API, lowest ban risk
- **Default to draft box**: `publish_csdn` defaults to `as_draft=True`, saving to CSDN's online draft box (not public) for your review
- **Session persistence**: login state saved as standard Playwright storageState JSON, git-ignored, prompts re-login when expired
- **Rate limiting**: applies only to **direct publish** (default 2/day, ≥ 30 min apart); saving drafts is unlimited
- **Failure evidence**: a screenshot is auto-saved to `.cookies/screenshots/` on publish failure
- **Centralized selectors**: `SELECTORS` dict at the top of `publisher.py`; key elements carry multiple fallback selectors, update there when CSDN changes its UI
- **UI-drift resilience**: fixed viewport + network-level ad blocking + auto overlay dismissal + multi-selector fallback + robust click retries, mitigating resolution changes / ads / minor redesigns
- **Self-diagnosis**: `diagnose_editor` probes each editor element and reports hits; run it when `publish_csdn` fails to find which selector CSDN changed
- **Asyncio-loop escape**: the MCP server runs tool functions inside an asyncio event loop, but Playwright's sync API refuses to start inside a running loop; the `util.run_in_thread` decorator dispatches browser tools to a fresh thread when a loop is running (and runs them directly in standalone scripts — zero overhead)
- **Paste the body via clipboard**: typing markdown char-by-char with `keyboard.type` triggers the editor's auto-indent/auto-list and mangles it (list `-` becomes `- -`, runaway code-block indent); instead the body is written to the clipboard and pasted with `Ctrl+V` in one shot, preserving the original markdown
- **Human-like pacing**: random 0.8-2.2s delays between actions to reduce anti-automation triggers

---

## ⚠️ Risks & compliance

| Risk | Description | Mitigation |
|------|------|------|
| Ban | CSDN rate-limits bulk publishing | Default 2/day, 30 min apart, varied content |
| Captcha | Login/publish may show a slider captcha | Automation can't solve it; manual handling (csdn_login opens a browser) |
| ToS | ToS prohibits unauthorized automated publishing | Plan A is lowest risk; default saves to draft box only |
| UI drift | CSDN editor changes | Multi-selector fallback + failure screenshots + `diagnose_editor` self-diagnosis |

**Pragmatic path**: start with the "writing" part only (zero risk), keep the final publish click manual. Enable auto-publish once stable.

---

## 💬 Feedback & contributions

If this project helps you, please:

1. ⭐ **Star** the repo: [csdn-mcp](https://gitee.com/gdouage/csdn-mcp)
2. 🐛 Open an [Issue](https://gitee.com/gdouage/csdn-mcp/issues) for problems
3. ✉️ Email for discussion: [3244940576@qq.com](mailto:3244940576@qq.com) (author: abbuibuibui)

Pull requests are welcome (please describe the intent and how you tested)~

---

## 📄 License

This project is open-sourced under the [MIT License](./LICENSE).

```text
Copyright (c) 2026 abbuibuibui
```

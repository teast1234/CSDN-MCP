"""Blog writing tools: generate_blog_scaffold and write_blog.

generate_blog_scaffold builds an SEO-optimized markdown skeleton tuned for
CSDN (keyword-front-loaded title, H2/H3 hierarchy, intro hook, code-block
placeholders, summary, tags). The AI agent fills it in.

write_blog packages finished content with YAML front-matter (title, summary,
tags, category, keywords, timestamps) and saves it to the local drafts
folder, returning the path the publisher later consumes.
"""

from __future__ import annotations

import re
import json
from datetime import datetime

from . import config


# Style presets — tune the scaffold's tone and section labels.
STYLE_PRESETS: dict[str, dict] = {
    "intro": {
        "label": "开源项目/MCP 介绍文",
        "sections": [
            ("痛点：为什么需要这个", "排比问句点出读者现状的麻烦"),
            ("这是什么", "一句话概括 + 特性表 + 仓库地址"),
            ("能力清单", "分类列出工具/功能，配表格"),
            ("核心能力详解", "每点小标题 + 表格/代码"),
            ("5 分钟上手", "环境要求 → 安装 → 配置 → 重启"),
            ("真实工作流演示", "你：… / AI：[调用 xxx] 对话式"),
            ("技术架构", "ASCII 框图 + 技术栈"),
            ("对比传统方式", "对比表，凸显本项目优势"),
            ("项目信息与反馈", "信息表 + Star 号召"),
        ],
        "intro_hint": "用排比问句点痛点：你还在…？还在…？再引出本项目，仓库地址前置。",
    },
    "technical": {
        "label": "技术教程",
        "sections": [
            ("背景与痛点", "为什么需要这个 / 现有方案的问题"),
            ("环境准备", "版本要求、依赖、前置知识"),
            ("核心实现", "分步骤讲解，每步配代码 + 注释"),
            ("进阶用法", "边界情况、性能、可配置项"),
            ("踩坑记录", "常见报错与解决办法"),
            ("总结", "回顾要点 + 扩展阅读"),
        ],
        "intro_hint": "用一句话点出读者能解决什么问题，再点出读完能拿到什么。",
    },
    "tutorial": {
        "label": "保姆级部署教程",
        "sections": [
            ("联想开场 + 效果展示", "动漫/科幻联想 + 先看效果再教做"),
            ("环境与工具", "版本号、下载链接、平台要求"),
            ("第一步：xxx", "下载地址→安装→配置→验证是否成功"),
            ("第二步：xxx", "注意！踩坑提醒单独成段"),
            ("第三步：xxx", ""),
            ("常见问题", "FAQ + 注意！提醒"),
            ("完整代码 / 配置", "贴出可运行的全量代码或配置文件"),
            ("致谢与资源汇总", "开源项目致谢 + 所有下载链接"),
        ],
        "intro_hint": "动漫/科幻联想开场：不知道大家是否想过…，先展示成品再承诺保姆级能复现。",
    },
    "analysis": {
        "label": "原理分析",
        "sections": [
            ("问题定义", "要分析什么、为什么重要"),
            ("现状梳理", "业界方案对比"),
            ("核心原理", "图解 + 关键代码/数据"),
            ("对比实验", "数据表 + 结论"),
            ("工程启示", "落地建议与取舍"),
            ("总结", "一句话结论 + 参考资料"),
        ],
        "intro_hint": "抛出一个反直觉的结论或问题，吸引技术读者往下看。",
    },
    "notes": {
        "label": "踩坑笔记",
        "sections": [
            ("问题现象", "报错信息 / 复现步骤"),
            ("排查过程", "试了什么、为什么不对"),
            ("根因", "一句话点透"),
            ("解决方案", "代码 + 命令"),
            ("延伸", "同类问题如何避免"),
        ],
        "intro_hint": "直接甩报错，让有同样问题的读者立刻知道这篇是写给他的。",
    },
    "general": {
        "label": "通用博文",
        "sections": [
            ("引言", "背景与动机"),
            ("主要内容", "分 2-4 个 H2 展开"),
            ("小结", "回顾 + 互动引导"),
        ],
        "intro_hint": "用一个具体场景或数字开场。",
    },
}


def _slugify(text: str, max_len: int = 50) -> str:
    """Make a filesystem-safe slug from a title (keep CJK chars)."""
    text = re.sub(r"[\\/:*?\"<>|]+", "-", text)
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-.")
    if len(text) > max_len:
        text = text[:max_len].rstrip("-")
    return text or "untitled"


def _title_suggestions(topic: str, keywords: list[str]) -> list[str]:
    """Generate 3 CSDN-style title suggestions matching the author's voice.

    Author patterns: '教你…' for tutorials, '让 AI…'/'用 MCP…' for intros,
    year tags ('2025最新'), difficulty promises ('小白也能学会'/'保姆级'),
    colon-separated main/sub title.
    """
    kw = keywords[0] if keywords else topic
    kw_short = kw[:12]
    year = datetime.now().year
    return [
        f"教你如何{kw_short}（绝对的保姆级教学，从0到1进行手搓）{year}最新教程",
        f"让 AI 帮你{kw_short}：{topic}，{year}最新实战指南",
        f"{kw_short}怎么做？{year}最新教程，小白也能学会的{topic}",
    ]


def _suggest_tags(topic: str, keywords: list[str]) -> list[str]:
    """Suggest 3-5 CSDN tags from topic + keywords."""
    tags: list[str] = []
    for kw in keywords:
        kw = kw.strip()
        if kw and kw not in tags:
            tags.append(kw)
    if topic and topic not in tags:
        tags.insert(0, topic)
    while len(tags) < 3:
        tags.append("编程")
    return tags[:5]


# ---------------------------------------------------------------------------
# Scaffold generation
# ---------------------------------------------------------------------------

def generate_blog_scaffold(
    topic: str,
    keywords: list[str] | None = None,
    style: str = "technical",
    tags: list[str] | None = None,
) -> dict:
    """Generate an SEO-optimized markdown scaffold for a CSDN blog post.

    Returns a markdown string the AI agent fills in. The scaffold follows
    CSDN ranking best practices: keyword-front-loaded title, H2/H3 hierarchy,
    intro hook, code-block placeholders with language hints, summary, and
    suggested tags.

    Args:
        topic: The blog topic / subject.
        keywords: SEO keywords (the first one is front-loaded into title ideas).
        style: Writing style preset — one of:
            "technical" (技术教程), "tutorial" (手把手教程),
            "analysis" (原理分析), "notes" (踩坑笔记), "general" (通用博文).
        tags: Optional pre-chosen tags; otherwise suggested from keywords.

    Returns:
        dict with {ok, topic, style, title_suggestions, tags_suggested, scaffold}
    """
    keywords = keywords or []
    style = style if style in STYLE_PRESETS else "technical"
    preset = STYLE_PRESETS[style]

    title_ideas = _title_suggestions(topic, keywords)
    tags_suggested = tags or _suggest_tags(topic, keywords)

    lines: list[str] = []
    lines.append("---")
    lines.append(f'title: "{title_ideas[0]}"  # 可从下方建议中选一个替换')
    lines.append(f'summary: ""  # 80-120 字，含主关键词，写完正文后补')
    lines.append(f"tags: {json.dumps(tags_suggested, ensure_ascii=False)}")
    lines.append(f'category: ""  # CSDN 分类，如 后端 / 前端 / 运维 / AI')
    lines.append(f"keywords: {json.dumps(keywords, ensure_ascii=False)}")
    lines.append(f'style: "{style}"')
    lines.append(f'visibility: "public"  # public / private / fans')
    lines.append("---")
    lines.append("")
    lines.append(f"# {title_ideas[0]}")
    lines.append("")
    lines.append("> 钩子：写在这里。提示 —— " + preset["intro_hint"])
    lines.append("")
    lines.append("（正文开头：100-150 字，点出问题 + 读完能拿到什么，自然带入主关键词）")
    lines.append("")

    lines.append("## 目录")
    lines.append("")
    for i, (h2, _) in enumerate(preset["sections"], 1):
        lines.append(f"{i}. [{h2}](#{h2})")
    lines.append("")

    for h2, hint in preset["sections"]:
        lines.append(f"## {h2}")
        if hint:
            lines.append(f"<!-- {hint} -->")
        lines.append("")
        lines.append(f"### {h2} - 要点一")
        lines.append("")
        lines.append("```python")
        lines.append("# 代码示例：注释说明每一步在做什么")
        lines.append("")
        lines.append("```")
        lines.append("")
        lines.append(f"### {h2} - 要点二")
        lines.append("")
        lines.append("（文字说明，配图或代码）")
        lines.append("")

    lines.append("## 总结")
    lines.append("")
    lines.append("- 要点 1")
    lines.append("- 要点 2")
    lines.append("- 要点 3")
    lines.append("")
    lines.append("> 如果对你有帮助，欢迎点赞收藏，评论区交流～")
    lines.append("")

    scaffold = "\n".join(lines)
    return {
        "ok": True,
        "topic": topic,
        "style": style,
        "style_label": preset["label"],
        "title_suggestions": title_ideas,
        "tags_suggested": tags_suggested,
        "scaffold": scaffold,
    }


# ---------------------------------------------------------------------------
# Front-matter helpers
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def _split_front_matter(text: str) -> tuple[str, dict]:
    """Return (body, front_matter_dict). body has no leading front-matter."""
    m = _FM_RE.match(text.lstrip())
    if not m:
        return text, {}
    raw_fm, body = m.group(1), m.group(2)
    return body, _parse_simple_yaml(raw_fm)


def _parse_simple_yaml(raw: str) -> dict:
    """Parse a tiny YAML subset (key: value, lists as JSON arrays)."""
    fm: dict = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if not (val.startswith('"') or val.startswith("'")) and "  #" in val:
            val = val.split("  #", 1)[0].strip()
        if val.startswith("[") and val.endswith("]"):
            try:
                fm[key] = json.loads(val)
                continue
            except json.JSONDecodeError:
                pass
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        fm[key] = val
    return fm


def _dump_front_matter(fm: dict) -> str:
    """Serialize front-matter to a --- delimited block."""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        elif v is None or v == "":
            lines.append(f'{k}: ""')
        elif isinstance(v, str) and (" " in v or '"' in v or "#" in v):
            esc = v.replace('"', '\\"')
            lines.append(f'{k}: "{esc}"')
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def _first_h1(body: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            return s[2:].strip()
    return ""


def _ensure_h1(body: str, title: str) -> str:
    """Make sure the body begins with an H1 equal to title."""
    stripped = body.lstrip()
    if stripped.startswith("# ") and not stripped.startswith("## "):
        return body
    return f"# {title}\n\n{body.strip()}"


def _extract_summary(body: str) -> str:
    """Pull the first non-heading, non-empty paragraph as a summary."""
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#") or s.startswith(">") or s.startswith("```") or s.startswith("|"):
            continue
        s = re.sub(r"\s+", " ", s)
        if len(s) > 120:
            s = s[:117] + "..."
        return s
    return ""


# ---------------------------------------------------------------------------
# write_blog — package content + front-matter, save to drafts
# ---------------------------------------------------------------------------

def write_blog(
    topic: str,
    content: str,
    keywords: list[str] | None = None,
    tags: list[str] | None = None,
    category: str = "",
    summary: str = "",
    style: str = "technical",
    visibility: str = "public",
    filename: str = "",
    overwrite: bool = False,
) -> dict:
    """Package blog content into a CSDN-ready markdown file and save it.

    Adds YAML front-matter (title, summary, tags, category, keywords, style,
    visibility, timestamps) and writes the file to the local drafts folder.
    The publish_csdn tool reads this same file later.

    If `content` already contains front-matter, the provided arguments override
    individual fields. If `summary` is empty, it is auto-extracted from the
    first non-heading paragraph (truncated to 120 chars).

    Args:
        topic: Blog title (used as H1 and filename slug if filename is empty).
        content: Markdown body. May include leading front-matter (--- ... ---).
        keywords: SEO keywords for the front-matter.
        tags: CSDN tags (3-5 recommended).
        category: CSDN category, e.g. "后端", "前端", "运维", "AI".
        summary: Article summary; auto-extracted if empty.
        style: Writing style (informational; stored in front-matter).
        visibility: "public", "private", or "fans".
        filename: Override filename (without .md). Auto-generated from title if empty.
        overwrite: If True, overwrite an existing draft with the same name.

    Returns:
        dict with {ok, file_path, filename, title, summary, tags, category, visibility, bytes}
    """
    keywords = keywords or []
    tags = tags or _suggest_tags(topic, keywords)

    body, existing_fm = _split_front_matter(content)
    title = topic or existing_fm.get("title") or _first_h1(body) or "untitled"
    if not summary:
        summary = existing_fm.get("summary") or _extract_summary(body)
    summary = (summary or "").strip()
    category = category or existing_fm.get("category", "")
    visibility = visibility or existing_fm.get("visibility", "public")
    style = style or existing_fm.get("style", "technical")

    now = datetime.now()
    fm = {
        "title": title,
        "summary": summary,
        "tags": tags,
        "category": category,
        "keywords": keywords,
        "style": style,
        "visibility": visibility,
        "created": now.isoformat(timespec="seconds"),
        "status": "draft",
    }

    body = _ensure_h1(body, title)
    out = _dump_front_matter(fm) + "\n" + body.strip() + "\n"

    if not filename:
        stamp = now.strftime("%Y%m%d-%H%M%S")
        filename = f"{stamp}-{_slugify(title)}"

    drafts_dir = config.get_drafts_dir()
    file_path = drafts_dir / f"{filename}.md"

    if file_path.exists() and not overwrite:
        i = 1
        while (drafts_dir / f"{filename}-{i}.md").exists():
            i += 1
        file_path = drafts_dir / f"{filename}-{i}.md"

    file_path.write_text(out, encoding="utf-8")

    return {
        "ok": True,
        "file_path": str(file_path),
        "filename": file_path.name,
        "title": title,
        "summary": summary,
        "tags": tags,
        "category": category,
        "visibility": visibility,
        "bytes": len(out.encode("utf-8")),
    }

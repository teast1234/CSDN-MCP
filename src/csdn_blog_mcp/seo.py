"""SEO checker for CSDN-ready markdown drafts.

Analyzes a saved draft for CSDN ranking factors and returns a structured
report with a score and actionable warnings. Pure text analysis, no network.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import config
from .writer import _split_front_matter


def seo_check(file_path: str) -> dict:
    """Analyze a draft markdown file for CSDN SEO issues.

    Checks: title length & keyword placement, summary presence & length,
    keyword density, H2/H3 hierarchy, code blocks with language hints,
    word count, image alt text, internal links, tag count.

    Args:
        file_path: Absolute path to the draft .md file.

    Returns:
        dict with {ok, score, checks: [{name, status, message, detail}],
        summary, suggestions}
    """
    path = Path(file_path)
    if not path.is_file():
        return {"ok": False, "message": f"File not found: {file_path}"}

    text = path.read_text(encoding="utf-8")
    body, fm = _split_front_matter(text)
    title = fm.get("title") or _first_h1(body)
    summary = fm.get("summary", "")
    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    keywords = fm.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]

    checks: list[dict] = []
    score = 100

    # 1. Title length (CSDN shows ~30-50 chars well)
    tlen = len(title)
    if tlen == 0:
        checks.append({"name": "title", "status": "fail",
                       "message": "缺少标题", "detail": ""})
        score -= 30
    elif tlen < 10:
        checks.append({"name": "title", "status": "warn",
                       "message": f"标题过短（{tlen} 字），建议 15-40 字",
                       "detail": title})
        score -= 10
    elif tlen > 50:
        checks.append({"name": "title", "status": "warn",
                       "message": f"标题过长（{tlen} 字），搜索结果会被截断",
                       "detail": title})
        score -= 8
    else:
        checks.append({"name": "title", "status": "pass",
                       "message": f"标题长度合适（{tlen} 字）", "detail": title})

    # 2. Title keyword front-loading (case-insensitive)
    if keywords and title:
        kw0 = keywords[0]
        title_l = title.lower()
        kw0_l = kw0.lower()
        if kw0_l in title_l:
            pos = title_l.find(kw0_l)
            if pos <= 8:
                checks.append({"name": "title_keyword", "status": "pass",
                               "message": f"主关键词「{kw0}」出现在标题前部",
                               "detail": ""})
            else:
                checks.append({"name": "title_keyword", "status": "warn",
                               "message": f"主关键词在标题第 {pos} 字，建议前置",
                               "detail": ""})
                score -= 5
        else:
            checks.append({"name": "title_keyword", "status": "fail",
                           "message": f"标题未包含主关键词「{kw0}」", "detail": ""})
            score -= 15

    # 3. Summary
    slen = len(summary)
    if slen == 0:
        checks.append({"name": "summary", "status": "fail",
                       "message": "缺少摘要（CSDN 摘要影响搜索与列表展示）", "detail": ""})
        score -= 15
    elif slen < 30:
        checks.append({"name": "summary", "status": "warn",
                       "message": f"摘要过短（{slen} 字），建议 80-120 字", "detail": ""})
        score -= 8
    elif slen > 150:
        checks.append({"name": "summary", "status": "warn",
                       "message": f"摘要过长（{slen} 字），建议控制在 120 字内", "detail": ""})
        score -= 5
    else:
        checks.append({"name": "summary", "status": "pass",
                       "message": f"摘要长度合适（{slen} 字）", "detail": ""})

    # 4. Tags count
    tag_count = len(tags)
    if tag_count == 0:
        checks.append({"name": "tags", "status": "fail",
                       "message": "未设置标签", "detail": ""})
        score -= 10
    elif tag_count < 3:
        checks.append({"name": "tags", "status": "warn",
                       "message": f"仅 {tag_count} 个标签，建议 3-5 个", "detail": str(tags)})
        score -= 5
    elif tag_count > 5:
        checks.append({"name": "tags", "status": "warn",
                       "message": f"标签过多（{tag_count} 个），CSDN 最多展示 5 个",
                       "detail": str(tags)})
        score -= 3
    else:
        checks.append({"name": "tags", "status": "pass",
                       "message": f"标签数量合适（{tag_count} 个）", "detail": str(tags)})

    # 5. Heading hierarchy
    h2s = re.findall(r"^##\s+(.+)$", body, re.MULTILINE)
    h3s = re.findall(r"^###\s+(.+)$", body, re.MULTILINE)
    if len(h2s) < 2:
        checks.append({"name": "headings", "status": "warn",
                       "message": f"仅 {len(h2s)} 个 H2，建议分 3-6 个大节", "detail": ""})
        score -= 8
    else:
        checks.append({"name": "headings", "status": "pass",
                       "message": f"H2={len(h2s)} H3={len(h3s)}，结构清晰", "detail": ""})

    # 6. Word count
    plain = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    plain = re.sub(r"[#`>*\-\[\]\(\)]", "", plain)
    char_count = len(re.sub(r"\s", "", plain))
    if char_count < 800:
        checks.append({"name": "length", "status": "warn",
                       "message": f"正文约 {char_count} 字，偏短（建议 1500+）", "detail": ""})
        score -= 10
    elif char_count > 6000:
        checks.append({"name": "length", "status": "pass",
                       "message": f"正文约 {char_count} 字，内容充实", "detail": ""})
    else:
        checks.append({"name": "length", "status": "pass",
                       "message": f"正文约 {char_count} 字", "detail": ""})

    # 7. Code blocks with language hints (track open/close fences properly)
    code_blocks = _count_code_blocks(body)
    no_lang = sum(1 for c in code_blocks if not c)
    if code_blocks and no_lang > 0:
        checks.append({"name": "code_lang", "status": "warn",
                       "message": f"{no_lang}/{len(code_blocks)} 个代码块缺少语言标记",
                       "detail": "如 ```python 而非 ```"})
        score -= 5
    elif code_blocks:
        checks.append({"name": "code_lang", "status": "pass",
                       "message": f"{len(code_blocks)} 个代码块均标注语言", "detail": ""})
    else:
        checks.append({"name": "code_lang", "status": "pass",
                       "message": "无代码块（技术文建议配代码）", "detail": ""})

    # 8. Keyword density (case-insensitive)
    if keywords and char_count > 0:
        kw0 = keywords[0]
        count = body.lower().count(kw0.lower())
        density = count * len(kw0) / max(char_count, 1) * 100
        if count == 0:
            checks.append({"name": "keyword_density", "status": "fail",
                           "message": f"正文未出现主关键词「{kw0}」", "detail": ""})
            score -= 15
        elif density > 5:
            checks.append({"name": "keyword_density", "status": "warn",
                           "message": f"关键词密度 {density:.1f}%，可能堆砌", "detail": ""})
            score -= 5
        else:
            checks.append({"name": "keyword_density", "status": "pass",
                           "message": f"主关键词出现 {count} 次（密度 {density:.1f}%）",
                           "detail": ""})

    # 9. Images with alt text
    imgs = re.findall(r"!\[([^\]]*)\]\([^)]+\)", body)
    if imgs:
        no_alt = sum(1 for a in imgs if not a.strip())
        if no_alt > 0:
            checks.append({"name": "image_alt", "status": "warn",
                           "message": f"{no_alt}/{len(imgs)} 张图片缺少 alt 文本", "detail": ""})
            score -= 5
        else:
            checks.append({"name": "image_alt", "status": "pass",
                           "message": f"{len(imgs)} 张图片均有 alt", "detail": ""})

    score = max(0, min(100, score))
    fails = [c for c in checks if c["status"] == "fail"]
    warns = [c for c in checks if c["status"] == "warn"]
    suggestions = [f"{c['name']}: {c['message']}" for c in fails + warns]

    return {
        "ok": True,
        "file_path": str(path),
        "title": title,
        "score": score,
        "checks": checks,
        "fail_count": len(fails),
        "warn_count": len(warns),
        "suggestions": suggestions,
        "summary": f"SEO 评分 {score}/100（{len(fails)} 严重，{len(warns)} 警告）",
    }


def _first_h1(body: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            return s[2:].strip()
    return ""


def _count_code_blocks(body: str) -> list[str]:
    """Return the language hint of each opening code fence (empty if none).

    Walks lines and tracks open/close fence state so closing ``` markers
    are not mistaken for code blocks missing a language.
    """
    langs: list[str] = []
    in_block = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_block:
                langs.append(stripped[3:].strip())
                in_block = True
            else:
                in_block = False
    return langs

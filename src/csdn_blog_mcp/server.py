"""CSDN Blog MCP Server - registers all tools with FastMCP."""

from __future__ import annotations

import os
import sys

# Ensure src is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP

from csdn_blog_mcp.writer import generate_blog_scaffold, write_blog
from csdn_blog_mcp.seo import seo_check
from csdn_blog_mcp.library import list_drafts, read_draft, delete_draft
from csdn_blog_mcp.auth import check_login, login, has_saved_session, clear_session
from csdn_blog_mcp.publisher import publish_csdn
from csdn_blog_mcp.stats import csdn_stats
from csdn_blog_mcp.style import get_style_guide
from csdn_blog_mcp import config

mcp = FastMCP("CSDN Blog MCP")


# ---------------------------------------------------------------------------
# Writing tools (zero risk)
# ---------------------------------------------------------------------------

@mcp.tool()
def tool_get_style_guide() -> dict:
    """Return the CSDN writing style guide (the MCP's own prompt).

    The guide was distilled from the author's published CSDN posts and
    documents the tone (address reader '你', casual but neutral, no personal
    persona), the two article types (intro vs. step-by-step tutorial),
    title patterns, opening hooks, required elements (tables, code blocks,
    emoji headers, '注意！' callouts, Star solicitation), SEO rules, and what
    to avoid. Call this BEFORE generate_blog_scaffold / write_blog so content
    matches the author's style.

    Returns:
        dict with {ok, path, guide} on success, or {ok, message} if missing.
    """
    return get_style_guide()


@mcp.tool()
def tool_generate_blog_scaffold(
    topic: str,
    keywords: list[str] | None = None,
    style: str = "technical",
    tags: list[str] | None = None,
) -> dict:
    """Generate an SEO-optimized markdown scaffold for a CSDN blog post.

    Returns a markdown skeleton tuned for CSDN ranking: keyword-front-loaded
    title ideas, H2/H3 hierarchy, intro hook, code-block placeholders, and
    suggested tags. Use this BEFORE writing to get a good structure, then fill
    it in and pass the result to write_blog.

    Tip: call get_style_guide first so the filled-in content matches the
    author's voice.

    Args:
        topic: The blog topic / subject.
        keywords: SEO keywords (the first one is front-loaded into title ideas).
        style: Writing style preset — "intro" (开源项目/MCP 介绍文),
            "tutorial" (保姆级部署教程), "technical", "analysis", "notes",
            or "general".
        tags: Optional pre-chosen tags; otherwise suggested from keywords.

    Returns:
        dict with {ok, topic, style, title_suggestions, tags_suggested, scaffold}
    """
    return generate_blog_scaffold(topic, keywords, style, tags)


@mcp.tool()
def tool_write_blog(
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
    The publish_csdn tool reads this same file later. If `content` already has
    front-matter, the arguments override individual fields. If `summary` is
    empty, it is auto-extracted from the first paragraph.

    Args:
        topic: Blog title (used as H1 and filename slug if filename is empty).
        content: Markdown body. May include leading front-matter (--- ... ---).
        keywords: SEO keywords for the front-matter.
        tags: CSDN tags (3-5 recommended).
        category: CSDN category, e.g. "后端", "前端", "运维", "AI".
        summary: Article summary; auto-extracted if empty.
        style: Writing style (informational; stored in front-matter).
        visibility: "public", "private", or "fans".
        filename: Override filename (without .md). Auto-generated if empty.
        overwrite: If True, overwrite an existing draft with the same name.

    Returns:
        dict with {ok, file_path, filename, title, summary, tags, category, visibility, bytes}
    """
    return write_blog(topic, content, keywords, tags, category, summary,
                      style, visibility, filename, overwrite)


@mcp.tool()
def tool_seo_check(file_path: str) -> dict:
    """Analyze a draft markdown file for CSDN SEO issues before publishing.

    Checks title length & keyword placement, summary, keyword density, H2/H3
    hierarchy, word count, code-block language hints, image alt text, and tag
    count. Returns a 0-100 score with actionable warnings.

    Args:
        file_path: Absolute path to the draft .md file.

    Returns:
        dict with {ok, score, checks, fail_count, warn_count, suggestions, summary}
    """
    return seo_check(file_path)


# ---------------------------------------------------------------------------
# Local draft library
# ---------------------------------------------------------------------------

@mcp.tool()
def tool_list_drafts() -> dict:
    """List all draft blog posts in the local drafts folder (newest first).

    Returns each draft's filename, title, summary, tags, created timestamp,
    and size. Use this to see what's ready to publish.

    Returns:
        dict with {ok, drafts: [...], count}
    """
    return list_drafts()


@mcp.tool()
def tool_read_draft(file_path: str) -> dict:
    """Read a draft markdown file and return its content + parsed metadata.

    Args:
        file_path: Absolute path, or just a filename resolved against the
            drafts folder.

    Returns:
        dict with {ok, file_path, title, summary, tags, category, keywords,
        visibility, status, created, content}
    """
    return read_draft(file_path)


@mcp.tool()
def tool_delete_draft(file_path: str) -> dict:
    """Delete a draft markdown file from the local drafts folder.

    Args:
        file_path: Absolute path or filename of the draft to delete.

    Returns:
        dict with {ok, message, file_path}
    """
    return delete_draft(file_path)


# ---------------------------------------------------------------------------
# CSDN publishing (Plan A — browser automation)
# ---------------------------------------------------------------------------

@mcp.tool()
def tool_check_csdn_login(headless: bool = True) -> dict:
    """Check whether the saved CSDN session is still logged in.

    Opens a browser (headless by default), loads www.csdn.net with the saved
    storage state, and reports login status. Call this before publish_csdn to
    avoid a failed publish due to an expired session.

    Args:
        headless: Run headless (default True for a quick check).

    Returns:
        dict with {ok, logged_in, needs_login, saved_session, message}
    """
    return check_login(headless=headless)


@mcp.tool()
def tool_csdn_login(headless: bool = False, timeout_ms: int = 180000) -> dict:
    """Open a visible browser to log into CSDN and save the session.

    First-time login MUST be visible (headless=False) so you can solve any
    captcha. After login is detected, the cookies + localStorage are saved
    so publish_csdn can run headless later. Complete the login in the browser
    window that opens.

    Args:
        headless: Must be False for first login (kept for flexibility).
        timeout_ms: How long to wait for login (default 3 minutes).

    Returns:
        dict with {ok, message, saved, path?}
    """
    return login(headless=headless, timeout_ms=timeout_ms)


@mcp.tool()
def tool_clear_csdn_session() -> dict:
    """Delete the saved CSDN session (forces a fresh login next time).

    Returns:
        dict with {ok, message}
    """
    return clear_session()


@mcp.tool()
def tool_publish_csdn(
    file_path: str,
    tags: list[str] | None = None,
    category: str = "",
    visibility: str = "",
    as_draft: bool = True,
    headless: bool = True,
    timeout_ms: int = 60000,
    skip_rate_limit: bool = False,
) -> dict:
    """Send a local draft to CSDN via browser automation (Plan A).

    By default (as_draft=True) saves the article to CSDN's online 草稿箱
    (draft box) WITHOUT publishing — you then review it in the browser and
    publish manually. Set as_draft=False to publish directly (public
    immediately, returns the article URL).

    Fills the CSDN markdown editor: title, body, tags, category, visibility,
    then clicks 存草稿 or 发布文章. Direct publish enforces a rate limit
    (default 2/day, min 30 min apart) to avoid anti-automation flags; saving
    drafts is not rate-limited.

    Requires a saved session — call csdn_login first. If the session expired,
    returns needs_login=True so you can re-run csdn_login.

    WARNING: This drives CSDN's web UI. Selectors may break when CSDN changes
    its editor; a screenshot is saved on failure to help diagnose. Respect
    CSDN's terms — keep frequency low and content genuine.

    Args:
        file_path: Absolute path to the draft .md file (from write_blog).
        tags: Override tags from the draft's front-matter (3-5 recommended).
        category: Override CSDN category (e.g. "后端").
        visibility: Override visibility — "public", "private", or "fans"
            (only meaningful when as_draft=False).
        as_draft: True (default) = save to CSDN draft box, not public.
            False = publish directly and return the article URL.
        headless: Run headless (default True). Set False to watch the action.
        timeout_ms: Per-action timeout in milliseconds.
        skip_rate_limit: Bypass the rate limit (use with care — risks a ban).
            Only applies when as_draft=False.

    Returns:
        dict with {ok, as_draft, message, title, draft_manage_url?, article_url?,
        screenshot?, needs_login?}
    """
    return publish_csdn(file_path, tags, category, visibility, as_draft,
                        headless, timeout_ms, skip_rate_limit)


@mcp.tool()
def tool_csdn_stats(article_url: str) -> dict:
    """Fetch view/like/comment/collect counts for a published CSDN article.

    Uses CSDN's public article-detail JSON endpoint (no login required).
    Call this after publish_csdn to track how a post is doing.

    Args:
        article_url: Full CSDN article URL
            (e.g. https://blog.csdn.net/<user>/article/details/<id>).

    Returns:
        dict with {ok, article_url, article_id, title, views, likes, comments,
        collects, publish_time}
    """
    return csdn_stats(article_url)


@mcp.tool()
def tool_rate_limit_status() -> dict:
    """Check the current publish rate-limit status without publishing.

    Returns whether a new publish is allowed, today's count, the last publish
    timestamp, and minutes since the last publish.

    Returns:
        dict with {allowed, reason, today_count, last_publish_ts, minutes_since_last}
    """
    return config.check_rate_limit()


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()

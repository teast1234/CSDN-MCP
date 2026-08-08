"""CSDN publisher via browser automation (Plan A) — with a resilience layer.

Drives the CSDN markdown editor with Playwright using a saved login session.
Resilience against UI drift, popups/ads, and resolution changes:
  - Block ad/tracker requests at the network layer so they never render.
  - Fixed viewport so layout is deterministic regardless of host resolution.
  - Dismiss common CSDN overlays (login/VIP/cookie/ad) before key actions.
  - Each key element has a FALLBACK LIST of selectors; tried in order.
  - Clicks scroll into view, retry after dismissing overlays, then force-click.
  - On failure: screenshot + selectors tried + page URL, for fast diagnosis.
  - diagnose_editor() probes the editor headless and reports which selectors
    still resolve, so UI drift can be caught BEFORE a real publish fails.
All selectors are centralized in SELECTORS so they can be updated when CSDN
changes its editor UI.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from . import config, auth
from .util import run_in_thread
from .writer import _split_front_matter

# Fixed viewport → deterministic layout regardless of the host screen.
VIEWPORT = {"width": 1280, "height": 800}

# Ad / tracker URL substrings to abort at the network layer so they never
# render and can never intercept a click.
AD_BLOCK_SUBSTRINGS = (
    "googlesyndication", "googleads", "doubleclick", "googletagmanager",
    "pos.baidu.com", "eclick.baidu.com", "dup.baidustatic.com",
    "/ad.", "/ads/", "adserver", "cnzz.com", "umeng",
    "csdn.net/pc_web/global/js/ad",
)

# Common CSDN overlay close buttons (login prompt, VIP upsell, cookie consent,
# ad close, "求更新"). Dismissed before key actions so they can't steal clicks.
OVERLAY_CLOSE_SELECTORS = [
    ".el-dialog__headerbtn",
    ".el-message-box__headerbtn",
    ".close-btn", ".closeBtn", ".ad-close", ".ad_close",
    ".layui-layer-close", ".modal-close",
    "button:has-text('关闭')",
    "button:has-text('我知道了')",
    "button:has-text('不再提示')",
    "button:has-text('暂不')",
    "a:has-text('关闭')",
    ".popup-close", ".dialog-close",
]

# Centralized selectors. Key elements use a LIST of fallbacks (tried in order)
# so a single class-name change won't break the flow.
SELECTORS = {
    "editor_url": "https://editor.csdn.net/md",
    # title: the visible display div; click it to focus the hidden backing input
    "title_display": [
        "div.article-bar__title-display",
        ".article-title",
        "[contenteditable][class*='title']",
        "h1[contenteditable]",
    ],
    "title_input": [
        "input.article-bar__title",
        "input[name='title']",
        "input[placeholder*='标题']",
    ],
    "title_default": "【无标题】",
    "content_editor": [
        ".editor__inner.markdown-highlighting",
        ".editor__inner",
        "[contenteditable][class*='editor']",
        "#editor",
    ],
    "save_draft_button": [
        "button.btn-save",
        "button:has-text('保存草稿')",
        ".toolbar button:has-text('草稿')",
    ],
    "save_draft_item": [
        "text=保存草稿",
        ".el-dropdown-menu li:has-text('保存草稿')",
        "li:has-text('保存草稿')",
    ],
    "publish_button": [
        "button.btn-publish",
        "button:has-text('发布文章')",
        "button:has-text('发布')",
    ],
    # Publish-dialog selectors (only used when as_draft=False)
    "tag_input": ["input[placeholder*='标签']", ".tag-input input", "#tags"],
    "category_input": ["input[placeholder*='分类']", ".category-input input"],
    "visibility_public": "text=公开",
    "visibility_private": "text=私密",
    "visibility_fans": "text=粉丝可见",
    "dialog_publish_button": [
        "button:has-text('发布')",
        ".dialog-footer button.btn-primary",
    ],
    "article_link": "a[href*='blog.csdn.net']",
    "draft_manage_url": "https://mp.csdn.net/mp_blog/manage",
    "success_toast": "text=成功, text=保存成功, text=发布成功, .el-message--success",
}


def _human_delay(min_s: float = 0.8, max_s: float = 2.2) -> None:
    """Sleep a random human-like interval between actions."""
    import random
    time.sleep(random.uniform(min_s, max_s))


def _block_ads(page) -> None:
    """Abort requests to known ad/tracker domains so they never render."""
    def handler(route):
        url = (route.request.url or "").lower()
        if any(s in url for s in AD_BLOCK_SUBSTRINGS):
            try:
                route.abort()
                return
            except Exception:
                pass
        try:
            route.continue_()
        except Exception:
            pass
    try:
        page.route("**/*", handler)
    except Exception:
        pass


def _dismiss_overlays(page) -> int:
    """Close any visible popup/ad/upsell that might intercept clicks."""
    closed = 0
    for sel in OVERLAY_CLOSE_SELECTORS:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=1000)
                _human_delay(0.2, 0.4)
                closed += 1
        except Exception:
            continue
    return closed


def _query_any(page, selectors):
    """Return the first matching element from a selector string or list."""
    if isinstance(selectors, str):
        selectors = [selectors]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                return el
        except Exception:
            continue
    return None


def _robust_click(page, selectors, label: str = "element") -> tuple[bool, str]:
    """Scroll into view and click; on failure dismiss overlays, retry, force-click."""
    el = _query_any(page, selectors)
    if not el:
        sels = selectors if isinstance(selectors, str) else list(selectors)
        return False, f"找不到{label}（尝试的选择器：{sels}）"
    try:
        el.scroll_into_view_if_needed(timeout=2000)
        el.click(timeout=3000)
        return True, ""
    except Exception as e:
        _dismiss_overlays(page)
        el = _query_any(page, selectors)
        if not el:
            return False, f"{label}重试时消失：{e}"
        try:
            el.click(force=True, timeout=3000)
            return True, ""
        except Exception as e2:
            return False, f"点击{label}失败（已关弹窗+强制点击）：{e2}"


def _new_context(pw, headless: bool, state):
    """Create a browser context with a fixed viewport + the saved session."""
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context(viewport=VIEWPORT, storage_state=state) \
        if state else browser.new_context(viewport=VIEWPORT)
    # Allow clipboard write so we can paste the markdown body in one shot
    # (typing char-by-char triggers the editor's auto-indent/auto-list and
    # mangles the markdown — doubled list markers, runaway code-block indent).
    try:
        context.grant_permissions(["clipboard-read", "clipboard-write"])
    except Exception:
        pass
    return browser, context


def _read_draft_for_publish(file_path: str) -> dict:
    """Read a draft and split it into metadata + body for the editor."""
    path = Path(file_path)
    if not path.is_file():
        return {"ok": False, "message": f"Draft not found: {file_path}"}
    text = path.read_text(encoding="utf-8")
    body, fm = _split_front_matter(text)
    title = fm.get("title") or _first_h1(body) or path.stem
    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    category = fm.get("category", "")
    visibility = fm.get("visibility", "public")
    return {
        "ok": True,
        "title": title,
        "content": body.strip(),
        "tags": tags,
        "category": category,
        "visibility": visibility,
    }


def _first_h1(body: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            return s[2:].strip()
    return ""


def _save_screenshot(page, label: str) -> str:
    """Save a diagnostic screenshot, return its path."""
    shots = config.get_screenshots_dir()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = shots / f"{stamp}-{label}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return ""


def _strip_h1(content: str) -> str:
    """Remove the leading H1 — CSDN's title field holds it separately."""
    lines = content.splitlines()
    if lines and lines[0].strip().startswith("# ") and not lines[0].strip().startswith("## "):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    return "\n".join(lines)


@run_in_thread
def diagnose_editor(headless: bool = True, timeout_ms: int = 30000) -> dict:
    """Open the CSDN editor headless and report which key selectors resolve.

    Use this to detect UI drift BEFORE a real publish fails. Returns, for each
    key element, whether a selector matched, plus a screenshot + page URL.
    Requires a saved session (call csdn_login first).
    """
    state = auth.load_storage_state()
    if state is None:
        return {"ok": False, "needs_login": True,
                "message": "No saved session. Call csdn_login first."}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "message": "Playwright is not installed."}
    try:
        with sync_playwright() as pw:
            browser, context = _new_context(pw, headless, state)
            page = context.new_page()
            _block_ads(page)
            page.goto(SELECTORS["editor_url"], timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            _dismiss_overlays(page)
            if "login" in page.url.lower():
                browser.close()
                return {"ok": False, "needs_login": True,
                        "message": "Session expired — redirected to login."}
            report = {}
            for key in ("title_display", "title_input", "content_editor",
                        "save_draft_button", "publish_button"):
                report[key] = "found" if _query_any(page, SELECTORS[key]) else "MISSING"
            shot = _save_screenshot(page, "diagnose")
            url = page.url
            browser.close()
            missing = [k for k, v in report.items() if v == "MISSING"]
            return {
                "ok": not missing,
                "page_url": url,
                "selectors": report,
                "missing": missing,
                "screenshot": shot,
                "message": ("所有关键选择器正常" if not missing
                            else f"UI 可能已改版，缺失：{missing}；请更新 publisher.py 的 SELECTORS"),
            }
    except Exception as e:
        return {"ok": False, "message": f"Diagnose failed: {e}"}


@run_in_thread
def publish_csdn(
    file_path: str,
    tags: list[str] | None = None,
    category: str = "",
    visibility: str = "",
    as_draft: bool = True,
    headless: bool = True,
    timeout_ms: int = 60000,
    skip_rate_limit: bool = False,
) -> dict:
    """Publish a local draft to CSDN via browser automation (Plan A).

    Opens the CSDN markdown editor with the saved login session, fills the
    title, pastes the body, sets tags/category/visibility, then either saves
    to CSDN's online draft box (default) or publishes directly. Enforces a
    rate limit (default 2/day, min 30 min apart) to avoid anti-automation flags.

    Saving to the draft box (as_draft=True) keeps the article private in your
    CSDN 草稿箱 so you can review it in the browser before manually publishing.
    Direct publish (as_draft=False) makes the article public immediately and
    returns its URL.

    Requires a saved session — call csdn_login first. If the session is
    expired, returns needs_login=True so the agent can re-run csdn_login.

    Args:
        file_path: Absolute path to the draft .md file (from write_blog).
        tags: Override tags from the draft's front-matter (3-5 recommended).
        category: Override CSDN category (e.g. "后端").
        visibility: Override visibility — "public", "private", or "fans".
            (Only meaningful when as_draft=False.)
        as_draft: If True (default), save to CSDN draft box (not public).
            If False, publish directly and return the article URL.
        headless: Run headless (default True). Set False to watch the publish.
        timeout_ms: Per-action timeout in milliseconds.
        skip_rate_limit: Bypass the rate limit (use with care — risks a ban).

    Returns:
        dict with {ok, article_url, message, screenshot?, needs_login?, as_draft}
    """
    # 1. Rate limit (only for direct publish; saving drafts is low-risk)
    if not as_draft and not skip_rate_limit:
        rl = config.check_rate_limit()
        if not rl["allowed"]:
            return {
                "ok": False,
                "message": rl["reason"],
                "rate_limited": True,
                "today_count": rl["today_count"],
                "as_draft": False,
            }

    # 2. Load draft
    draft = _read_draft_for_publish(file_path)
    if not draft["ok"]:
        return draft
    if tags is not None:
        draft["tags"] = tags
    if category:
        draft["category"] = category
    if visibility:
        draft["visibility"] = visibility

    # 3. Session
    state = auth.load_storage_state()
    if state is None:
        return {
            "ok": False,
            "message": "No saved session. Call csdn_login first to log in.",
            "needs_login": True,
        }

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "message": "Playwright is not installed. Run: pip install playwright && playwright install chromium",
        }

    body_for_editor = _strip_h1(draft["content"])
    try:
        with sync_playwright() as pw:
            browser, context = _new_context(pw, headless, state)
            page = context.new_page()
            _block_ads(page)

            # 4. Open the standalone markdown editor
            page.goto(SELECTORS["editor_url"], timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)  # let the editor fully render
            _human_delay()
            _dismiss_overlays(page)
            # Detect expired session -> redirected to login
            if "login" in page.url.lower() or (
                page.query_selector("text=登录") and not _query_any(page, SELECTORS["title_input"])
            ):
                browser.close()
                return {
                    "ok": False,
                    "message": "Session expired — redirected to login. Call csdn_login again.",
                    "needs_login": True,
                    "as_draft": as_draft,
                }

            # 5. Title — the visible title is a display div; clicking it focuses a
            # hidden backing input. Click the display div, Ctrl+A + Delete + type.
            disp_el = _query_any(page, SELECTORS["title_display"])
            if not disp_el:
                shot = _save_screenshot(page, "no-title-input")
                browser.close()
                return {"ok": False, "message": f"找不到标题显示框（CSDN 编辑器改版？）页面：{page.url}",
                        "screenshot": shot, "as_draft": as_draft}
            title_ok = False
            err = ""
            try:
                disp_el.click()
                _human_delay(0.3, 0.6)
                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
                page.keyboard.type(draft["title"], delay=15)
                _human_delay(0.5, 0.8)
                # Verify via the backing input value (try each fallback selector)
                for s in SELECTORS["title_input"]:
                    try:
                        got = page.eval_on_selector(s, "e => e.value")
                        if got and got.strip():
                            title_ok = True
                            break
                    except Exception:
                        continue
            except Exception as e1:
                err = str(e1)
            if not title_ok:
                shot = _save_screenshot(page, "title-fill-failed")
                browser.close()
                return {"ok": False, "message": f"标题填写失败 ({err}) 页面：{page.url}",
                        "screenshot": shot, "as_draft": as_draft}
            _human_delay()

            # 6. Content — the editor is a contenteditable div; clear the
            # default template (@[TOC] / 欢迎使用Markdown编辑器) then type.
            editor = _query_any(page, SELECTORS["content_editor"])
            if not editor:
                shot = _save_screenshot(page, "no-content-editor")
                browser.close()
                return {"ok": False, "message": f"找不到正文编辑区 页面：{page.url}",
                        "screenshot": shot, "as_draft": as_draft}
            editor.click()
            _human_delay(0.5, 1.0)
            page.keyboard.press("Control+a")
            page.keyboard.press("Delete")
            _human_delay(0.3, 0.6)
            # Paste the body via clipboard in one shot. Typing char-by-char
            # (page.keyboard.type) triggers the editor's auto-indent / auto-list
            # and mangles markdown (doubled "- " list markers, runaway
            # indentation inside code blocks, extra blank lines).
            pasted = False
            try:
                page.evaluate("(t) => navigator.clipboard.writeText(t)", body_for_editor)
                page.keyboard.press("Control+v")
                _human_delay(0.8, 1.4)
                pasted = True
            except Exception:
                pass
            if not pasted:
                page.keyboard.type(body_for_editor, delay=3)
            _human_delay()

            # 7. Save as draft OR publish directly.
            # In this editor, tags/category/visibility live in the PUBLISH
            # dialog, so a draft only needs title + content + 保存草稿.
            if as_draft:
                # 保存草稿 button opens a dropdown (保存草稿 / 保存并预览);
                # click the button then the 保存草稿 item in the popover.
                _dismiss_overlays(page)
                draft_btn = _query_any(page, SELECTORS["save_draft_button"])
                if not draft_btn:
                    shot = _save_screenshot(page, "no-draft-btn")
                    browser.close()
                    return {"ok": False, "message": f"找不到存草稿按钮（CSDN 编辑器改版？）页面：{page.url}",
                            "screenshot": shot, "as_draft": True}
                try:
                    draft_btn.scroll_into_view_if_needed(timeout=2000)
                    draft_btn.click(timeout=3000)
                except Exception:
                    draft_btn.click(force=True, timeout=3000)
                _human_delay(0.5, 1.2)
                # Click the 保存草稿 item in the dropdown popover
                item = _query_any(page, SELECTORS["save_draft_item"])
                if item:
                    try:
                        item.click()
                    except Exception:
                        item.click(force=True)
                _human_delay(2, 4)
                # Success may show as a toast (保存成功) or a status line
                # (已保存 / Article saved). Check broadly.
                page_text = page.inner_text("body")
                saved = any(s in page_text for s in ("保存成功", "已保存", "saved", "Article saved"))
                shot = "" if saved else _save_screenshot(page, "draft-uncertain")
                browser.close()
                if saved:
                    return {
                        "ok": True,
                        "as_draft": True,
                        "title": draft["title"],
                        "draft_manage_url": SELECTORS["draft_manage_url"],
                        "message": "已存入 CSDN 草稿箱，请到 mp.csdn.net 内容管理-草稿箱 审阅后手动发布",
                    }
                return {
                    "ok": True,
                    "as_draft": True,
                    "title": draft["title"],
                    "draft_manage_url": SELECTORS["draft_manage_url"],
                    "message": "已点击存草稿，未检测到明确成功提示，请到 mp.csdn.net 草稿箱确认",
                    "screenshot": shot,
                }

            # Direct publish — click 发布文章 to open the settings dialog.
            _dismiss_overlays(page)
            ok, msg = _robust_click(page, SELECTORS["publish_button"], "发布按钮")
            if not ok:
                shot = _save_screenshot(page, "no-publish-btn")
                browser.close()
                return {"ok": False, "message": f"{msg} 页面：{page.url}",
                        "screenshot": shot, "as_draft": False}
            _human_delay(2, 4)

            # Tags in the publish dialog (best-effort)
            for tag in draft["tags"][:5]:
                tag_el = _query_any(page, SELECTORS["tag_input"])
                if tag_el:
                    try:
                        tag_el.click()
                        tag_el.type(tag, delay=20)
                        _human_delay(0.3, 0.8)
                        page.keyboard.press("Enter")
                        _human_delay(0.3, 0.6)
                    except Exception:
                        pass

            # Category (best-effort)
            if draft["category"]:
                cat_el = _query_any(page, SELECTORS["category_input"])
                if cat_el:
                    try:
                        cat_el.click()
                        _human_delay()
                        cat_el.type(draft["category"], delay=20)
                        page.keyboard.press("Enter")
                        _human_delay()
                    except Exception:
                        pass

            # Visibility (best-effort)
            vis = draft["visibility"]
            vis_sel = {
                "public": SELECTORS["visibility_public"],
                "private": SELECTORS["visibility_private"],
                "fans": SELECTORS["visibility_fans"],
            }.get(vis)
            if vis_sel and vis != "public":
                try:
                    el = page.query_selector(vis_sel)
                    if el:
                        el.click()
                        _human_delay()
                except Exception:
                    pass

            # Confirm publish inside the dialog
            dialog_pub = _query_any(page, SELECTORS["dialog_publish_button"])
            if not dialog_pub:
                shot = _save_screenshot(page, "no-dialog-publish")
                browser.close()
                return {"ok": False, "message": f"发布对话框中找不到确认发布按钮 页面：{page.url}",
                        "screenshot": shot, "as_draft": False}
            with page.expect_navigation(timeout=timeout_ms, wait_until="domcontentloaded"):
                dialog_pub.click()
            _human_delay(2, 4)

            final_url = page.url
            success = ("blog.csdn.net" in final_url) or ("post" in final_url)
            article_url = final_url

            link = page.query_selector(SELECTORS["article_link"])
            if link:
                href = link.get_attribute("href") or ""
                if href and "blog.csdn.net" in href:
                    article_url = href
                    success = True

            browser.close()

            if success:
                config.record_publish(article_url, draft["title"])
                return {
                    "ok": True,
                    "as_draft": False,
                    "article_url": article_url,
                    "title": draft["title"],
                    "message": f"已发布：{article_url}",
                }
            return {
                "ok": False,
                "as_draft": False,
                "article_url": article_url,
                "message": "发布后未确认成功，请人工检查 URL",
            }
    except Exception as e:
        return {"ok": False, "message": f"Publish failed: {e}"}

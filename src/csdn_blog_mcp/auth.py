"""CSDN login state management.

Handles the persistent browser context (cookies + localStorage) used by
the publisher. The first login is headful so the user can solve any captcha;
after that, the saved storage state lets publishing run headless.

Storage state is saved as Playwright's standard JSON format at the path from
config.get_cookie_store(). It is git-ignored and should be treated as a
secret (it contains session cookies).
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config

CSDN_HOME = "https://www.csdn.net/"
CSDN_EDITOR = "https://mp.csdn.net/mp_blog/creator/editor"


def save_storage_state(state: dict) -> dict:
    """Persist a Playwright storageState dict to the cookie store.

    Args:
        state: A Playwright storageState object (cookies + origins/localStorage).

    Returns:
        dict with {ok, message, path}
    """
    path = config.get_cookie_store()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "message": f"Session saved to {path.name}", "path": str(path)}


def load_storage_state() -> dict | None:
    """Load the saved storage state, or None if not present/invalid."""
    path = config.get_cookie_store()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def has_saved_session() -> bool:
    """True if a (possibly valid) session file exists on disk."""
    return config.get_cookie_store().is_file()


def clear_session() -> dict:
    """Delete the saved session (forces a fresh login next time)."""
    path = config.get_cookie_store()
    if path.is_file():
        path.unlink()
        return {"ok": True, "message": "Session cleared"}
    return {"ok": True, "message": "No session to clear"}


def check_login(headless: bool = True, timeout_ms: int = 30000) -> dict:
    """Open a browser, load CSDN, and report whether the user is logged in.

    Uses the saved storage state if available. Detects login by looking for
    the login link vs. an avatar/account element on www.csdn.net.

    Args:
        headless: Run the browser headless (default True for a quick check).
        timeout_ms: Navigation timeout in milliseconds.

    Returns:
        dict with {ok, logged_in, message, needs_login, saved_session}
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "message": "Playwright is not installed. Run: pip install playwright && playwright install chromium",
        }

    state = load_storage_state()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context(storage_state=state) if state else browser.new_context()
            page = context.new_page()
            page.goto(CSDN_HOME, timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)

            # Heuristics: logged-in users have an avatar / "我的博客" link;
            # logged-out users see a "登录" button.
            logged_in = False
            for sel in ["a.avatar", ".user-avatar", "[class*=avatar]", "a[href*='/u/']"]:
                if page.query_selector(sel):
                    logged_in = True
                    break
            if not logged_in and page.query_selector("text=登录"):
                logged_in = False

            browser.close()
            return {
                "ok": True,
                "logged_in": logged_in,
                "needs_login": not logged_in,
                "saved_session": state is not None,
                "message": "已登录" if logged_in else "未登录，请先调用 csdn_login",
            }
    except Exception as e:
        return {"ok": False, "message": f"Login check failed: {e}", "logged_in": False}


def login(headless: bool = False, timeout_ms: int = 180000) -> dict:
    """Open a visible browser for the user to log into CSDN manually.

    After login, the storage state (cookies + localStorage) is saved so
    subsequent publish_csdn calls can run headless. The user should log in,
    solve any captcha, then close the browser window OR the function saves
    automatically once a logged-in state is detected.

    Args:
        headless: Must be False for first login (user needs to see the page).
            Kept as a parameter for flexibility.
        timeout_ms: How long to wait for the user to finish logging in
            (default 3 minutes).

    Returns:
        dict with {ok, message, saved}
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "message": "Playwright is not installed. Run: pip install playwright && playwright install chromium",
        }

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            page.goto(CSDN_HOME, timeout=60000, wait_until="domcontentloaded")

            # Poll for logged-in state up to timeout_ms
            import time
            deadline = time.time() + timeout_ms / 1000
            logged_in = False
            while time.time() < deadline:
                page.wait_for_timeout(2000)
                for sel in ["a.avatar", ".user-avatar", "[class*=avatar]", "a[href*='/u/']"]:
                    if page.query_selector(sel):
                        logged_in = True
                        break
                if logged_in:
                    break

            if not logged_in:
                browser.close()
                return {
                    "ok": False,
                    "message": "Login not detected within timeout. Try again and complete login in the browser window.",
                    "saved": False,
                }

            state = context.storage_state()
            browser.close()
            res = save_storage_state(state)
            return {"ok": True, "message": res["message"], "saved": True, "path": res["path"]}
    except Exception as e:
        return {"ok": False, "message": f"Login failed: {e}", "saved": False}

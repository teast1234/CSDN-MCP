"""Path and configuration management for csdn-blog-mcp.

Resolves all on-disk locations (drafts folder, cookie store, rate-limit log)
relative to the server package, so the MCP works regardless of the agent's
current working directory.

Resolution order for the data root:
  1. CSDN_BLOG_HOME environment variable
  2. <package_dir>/../..  (i.e. the project root next to src/)
"""

from __future__ import annotations

import os
import sys
import json
import time
import platform
from pathlib import Path


def _project_root() -> Path:
    """Return the project root (parent of src/)."""
    return Path(__file__).resolve().parent.parent.parent


def get_data_root() -> Path:
    """Return the data root directory (drafts, cookies, logs live here)."""
    env = os.environ.get("CSDN_BLOG_HOME")
    if env:
        root = Path(env).expanduser().resolve()
    else:
        root = _project_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_drafts_dir() -> Path:
    """Return the drafts directory where generated blog posts are saved."""
    drafts = get_data_root() / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    return drafts


def get_cookie_store() -> Path:
    """Return the path to the CSDN cookie/session store (JSON file).

    This file contains login cookies and must NOT be committed.
    """
    store = get_data_root() / ".cookies"
    store.mkdir(parents=True, exist_ok=True)
    return store / "csdn_session.json"


def get_rate_log() -> Path:
    """Return the path to the publish rate-limit log."""
    return get_data_root() / ".cookies" / "publish_log.json"


def get_screenshots_dir() -> Path:
    """Return the directory for diagnostic screenshots on publish failure."""
    shots = get_data_root() / ".cookies" / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    return shots


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

# Defaults tuned to look human and avoid CSDN anti-automation flags.
DEFAULT_DAILY_LIMIT = 2
DEFAULT_MIN_INTERVAL_MIN = 30


def read_publish_log() -> dict:
    """Read the publish history log. Returns {} if missing/corrupt."""
    path = get_rate_log()
    if not path.is_file():
        return {"publishes": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"publishes": []}


def write_publish_log(data: dict) -> None:
    path = get_rate_log()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def check_rate_limit(
    daily_limit: int = DEFAULT_DAILY_LIMIT,
    min_interval_min: int = DEFAULT_MIN_INTERVAL_MIN,
) -> dict:
    """Check whether a new publish is allowed under the rate limit.

    Returns a dict:
        {allowed: bool, reason: str,
         today_count: int, last_publish_ts: float|None,
         minutes_since_last: float|None}
    """
    log = read_publish_log()
    now = time.time()
    publishes = log.get("publishes", [])

    today_count = 0
    last_ts: float | None = None
    for entry in publishes:
        ts = entry.get("timestamp", 0)
        if now - ts < 24 * 3600:
            today_count += 1
        if ts > (last_ts or 0):
            last_ts = ts

    if today_count >= daily_limit:
        return {
            "allowed": False,
            "reason": f"Daily limit reached ({today_count}/{daily_limit}). "
            f"Wait until 24h since the first of today's publishes elapses.",
            "today_count": today_count,
            "last_publish_ts": last_ts,
            "minutes_since_last": (now - last_ts) / 60 if last_ts else None,
        }

    if last_ts is not None:
        minutes_since = (now - last_ts) / 60
        if minutes_since < min_interval_min:
            wait = min_interval_min - minutes_since
            return {
                "allowed": False,
                "reason": f"Too soon after last publish. Wait ~{wait:.0f} more "
                f"minutes (min interval {min_interval_min} min).",
                "today_count": today_count,
                "last_publish_ts": last_ts,
                "minutes_since_last": minutes_since,
            }

    return {
        "allowed": True,
        "reason": "OK",
        "today_count": today_count,
        "last_publish_ts": last_ts,
        "minutes_since_last": (now - last_ts) / 60 if last_ts else None,
    }


def record_publish(article_url: str, title: str) -> None:
    """Append a publish event to the rate-limit log."""
    log = read_publish_log()
    log.setdefault("publishes", []).append(
        {
            "timestamp": time.time(),
            "url": article_url,
            "title": title,
        }
    )
    write_publish_log(log)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def is_windows() -> bool:
    return sys.platform == "win32"


def default_browser_headless() -> bool:
    """Whether to run the browser headless by default on this platform.

    First-time login must always be headful (the user needs to see and solve
    any captcha). After a session is saved, headless is fine for publishing.
    """
    # On headless servers there's no display anyway; keep True except on
    # desktop Windows/macOS/Linux where a visible browser is friendlier.
    return False

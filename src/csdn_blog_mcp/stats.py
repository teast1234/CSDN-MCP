"""CSDN article stats via the public article-detail API.

CSDN exposes a public JSON endpoint for article details that includes view,
like, comment, and collect counts. No auth needed for public articles.
"""

from __future__ import annotations

import re
import json

CSDN_API = "https://blog.csdn.net/phoenix/web/article/details"


def _extract_article_id(article_url: str) -> str | None:
    """Pull the numeric article id from a CSDN article URL.

    Accepts forms like:
      https://blog.csdn.net/<user>/article/details/<id>
      https://blog.csdn.net/<user>/article/details/<id>?...
    """
    m = re.search(r"/article/details/(\d+)", article_url)
    return m.group(1) if m else None


def csdn_stats(article_url: str) -> dict:
    """Fetch view/like/comment/collect counts for a published CSDN article.

    Uses CSDN's public article-detail JSON endpoint (no login required).
    Useful after publish_csdn to track how a post is doing.

    Args:
        article_url: Full CSDN article URL
            (e.g. https://blog.csdn.net/<user>/article/details/<id>).

    Returns:
        dict with {ok, article_url, article_id, title, views, likes, comments,
        collects, raw}
    """
    article_id = _extract_article_id(article_url)
    if not article_id:
        return {"ok": False, "message": f"无法从 URL 解析文章 ID: {article_url}"}

    try:
        import httpx
    except ImportError:
        return {"ok": False, "message": "httpx 未安装。运行: pip install httpx"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Referer": article_url,
        "Accept": "application/json, text/plain, */*",
    }
    url = f"{CSDN_API}?id={article_id}"
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            r = client.get(url, headers=headers)
        if r.status_code != 200:
            return {"ok": False, "message": f"HTTP {r.status_code}", "article_id": article_id}
        data = r.json()
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        return {"ok": False, "message": f"请求失败: {e}", "article_id": article_id}

    code = data.get("code")
    if code != 200:
        return {"ok": False, "message": f"CSDN 返回 code={code}: {data.get('message', '')}",
                "article_id": article_id, "raw": data}

    item = data.get("data", {})
    return {
        "ok": True,
        "article_url": article_url,
        "article_id": article_id,
        "title": item.get("title", ""),
        "views": item.get("viewCount", 0),
        "likes": item.get("diggCount", 0) or item.get("likeCount", 0),
        "comments": item.get("commentCount", 0),
        "collects": item.get("collectCount", 0),
        "publish_time": item.get("createTime", ""),
        "raw": item,
    }

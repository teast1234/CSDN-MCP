"""Local draft library: list, read, delete draft markdown files.

Drafts live in the configured drafts folder (see config.get_drafts_dir).
Each draft is a markdown file with YAML front-matter written by write_blog.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import config
from .writer import _split_front_matter


def list_drafts() -> dict:
    """List all draft blog posts in the local drafts folder.

    Returns each draft's filename, title, summary, tags, created timestamp,
    size, and status. Sorted newest-first.

    Returns:
        dict with {ok, drafts: [{filename, file_path, title, summary, tags,
        category, created, status, size_bytes}], count}
    """
    drafts_dir = config.get_drafts_dir()
    items = []
    for p in sorted(drafts_dir.glob("*.md"), key=os.path.getmtime, reverse=True):
        meta = _read_meta(p)
        items.append({
            "filename": p.name,
            "file_path": str(p),
            "title": meta.get("title", p.stem),
            "summary": meta.get("summary", ""),
            "tags": meta.get("tags", []),
            "category": meta.get("category", ""),
            "created": meta.get("created", ""),
            "status": meta.get("status", "draft"),
            "size_bytes": p.stat().st_size,
        })
    return {"ok": True, "drafts": items, "count": len(items)}


def read_draft(file_path: str) -> dict:
    """Read a draft markdown file and return its content + parsed metadata.

    Args:
        file_path: Absolute path to the draft .md file (or just a filename,
            resolved against the drafts folder).

    Returns:
        dict with {ok, file_path, title, summary, tags, category, keywords,
        visibility, status, created, content}
    """
    path = _resolve(file_path)
    if path is None:
        return {"ok": False, "message": f"Draft not found: {file_path}"}
    text = path.read_text(encoding="utf-8")
    body, fm = _split_front_matter(text)
    return {
        "ok": True,
        "file_path": str(path),
        "title": fm.get("title", ""),
        "summary": fm.get("summary", ""),
        "tags": fm.get("tags", []),
        "category": fm.get("category", ""),
        "keywords": fm.get("keywords", []),
        "visibility": fm.get("visibility", "public"),
        "status": fm.get("status", "draft"),
        "created": fm.get("created", ""),
        "content": body.strip(),
    }


def delete_draft(file_path: str) -> dict:
    """Delete a draft markdown file from the local drafts folder.

    Args:
        file_path: Absolute path or filename of the draft to delete.

    Returns:
        dict with {ok, message, file_path}
    """
    path = _resolve(file_path)
    if path is None:
        return {"ok": False, "message": f"Draft not found: {file_path}"}
    path.unlink()
    return {"ok": True, "message": f"Deleted {path.name}", "file_path": str(path)}


def _resolve(file_path: str) -> Path | None:
    p = Path(file_path)
    if not p.is_absolute():
        p = config.get_drafts_dir() / file_path
    return p if p.is_file() else None


def _read_meta(path: Path) -> dict:
    try:
        _, fm = _split_front_matter(path.read_text(encoding="utf-8"))
        return fm
    except (OSError, UnicodeDecodeError):
        return {}

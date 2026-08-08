"""Style guide loader — returns the writing-style prompt derived from the
author's own published CSDN posts, so the MCP can write in that voice.

The guide lives at the project root as STYLE_GUIDE.md.
"""

from __future__ import annotations

from pathlib import Path

# src/csdn_blog_mcp/style.py -> project root
_GUIDE_PATH = Path(__file__).resolve().parent.parent.parent / "STYLE_GUIDE.md"


def get_style_guide() -> dict:
    """Load and return the CSDN writing style guide (the MCP's own prompt).

    The guide was distilled from the author's published posts and documents
    voice, the two article types (intro vs. step-by-step tutorial), title
    patterns, opening hooks, required elements, SEO rules, and what to avoid.
    The AI agent should call this BEFORE generate_blog_scaffold / write_blog so
    the content matches the author's style.

    Returns:
        dict with {ok, path, guide} on success, or {ok, message} if missing.
    """
    try:
        text = _GUIDE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "ok": False,
            "message": f"Style guide not found at {_GUIDE_PATH}",
        }
    return {"ok": True, "path": str(_GUIDE_PATH), "guide": text}

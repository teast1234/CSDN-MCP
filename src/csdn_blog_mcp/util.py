"""Small shared utilities.

``run_in_thread`` lets browser-automation functions use Playwright's *sync*
API from inside the MCP server. The MCP server runs tool functions within a
live asyncio event loop, and Playwright's sync API refuses to start inside a
running loop ("It looks like you are using Playwright Sync API inside the
asyncio loop"). By re-running the wrapped function in a brand-new daemon
thread, Playwright gets a clean thread with no running loop.

When there is no running loop (e.g. the standalone ``_run_publish.py`` script),
the wrapper just calls the function directly — no extra thread, no overhead.
"""

from __future__ import annotations

import asyncio
import functools
import threading
from typing import Callable, TypeVar

T = TypeVar("T")


def run_in_thread(fn: Callable[..., T]) -> Callable[..., T]:
    """Decorator: run ``fn`` in a fresh thread if called inside an asyncio loop.

    If no asyncio loop is running in the current thread, ``fn`` runs directly
    (zero overhead, normal stack traces). If a loop IS running, ``fn`` runs in
    a short-lived daemon thread and its result/exception is propagated back.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return fn(*args, **kwargs)

        box: dict = {}

        def _target():
            try:
                box["result"] = fn(*args, **kwargs)
            except BaseException as exc:  # noqa: BLE001 - re-raised below
                box["error"] = exc

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join()
        if "error" in box:
            raise box["error"]
        return box.get("result")

    return wrapper

"""Background-thread + queue plumbing for the Tk main loop (FR-023).

A worker thread runs ``target(*args, **kwargs)`` and pushes its outcome onto a
``queue.Queue``. The Tk main thread polls that queue via ``root.after(50, drain)``
so the UI never blocks on I/O and exceptions are funneled to ``on_error`` on the
main thread (never raised inside Tk callbacks).

Pure stdlib. The ``root`` parameter only needs an ``after(delay, callback)``
method, so tests can pass a fake recorder.
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Protocol


class _Afterable(Protocol):
    def after(self, ms: int, callback: Callable[[], None]) -> Any: ...


_DRAIN_INTERVAL_MS = 50


def run_in_background(
    target: Callable[..., Any],
    *args: Any,
    on_done: Callable[[Any], None],
    on_error: Callable[[BaseException], None],
    root: _Afterable,
    **kwargs: Any,
) -> threading.Thread:
    """Run ``target(*args, **kwargs)`` on a worker thread.

    On completion, ``on_done(result)`` is invoked on the main (Tk) thread.
    On any exception, ``on_error(exc)`` is invoked on the main (Tk) thread.
    Both callbacks are drained from the queue via ``root.after``.

    Returns the spawned :class:`threading.Thread` so callers can join in tests.
    """
    q: "queue.Queue[tuple[str, Any]]" = queue.Queue()

    def _worker() -> None:
        try:
            result = target(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 — funnel everything
            q.put(("error", exc))
        else:
            q.put(("done", result))

    def _drain() -> None:
        try:
            kind, payload = q.get_nowait()
        except queue.Empty:
            root.after(_DRAIN_INTERVAL_MS, _drain)
            return
        if kind == "done":
            on_done(payload)
        else:
            on_error(payload)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    root.after(_DRAIN_INTERVAL_MS, _drain)
    return thread

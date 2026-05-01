"""Unit tests for pbir_validator.gui.workers (T018)."""

from __future__ import annotations

from typing import Any, Callable

import pytest

from pbir_validator.gui import workers


class _FakeRoot:
    """Records ``after()`` calls and runs them synchronously."""

    def __init__(self, max_drains: int = 50) -> None:
        self.calls: list[tuple[int, Callable[[], None]]] = []
        self._max = max_drains

    def after(self, ms: int, callback: Callable[[], None]) -> Any:
        self.calls.append((ms, callback))
        # Run the queued drain immediately, but cap to avoid runaway loops if
        # the worker hasn't completed yet (tests should join the thread first).
        if len(self.calls) <= self._max:
            callback()
        return None


def test_run_in_background_invokes_on_done_with_return_value() -> None:
    root = _FakeRoot()
    captured: dict[str, Any] = {}

    def target(x: int, y: int) -> int:
        return x + y

    thread = workers.run_in_background(
        target,
        2,
        3,
        on_done=lambda r: captured.setdefault("result", r),
        on_error=lambda e: captured.setdefault("error", e),
        root=root,
    )
    thread.join(timeout=2)

    # Drain any pending callbacks the thread queued after we last looped
    while root.calls and "result" not in captured and "error" not in captured:
        _, cb = root.calls.pop(0)
        cb()

    assert captured.get("result") == 5
    assert "error" not in captured


def test_run_in_background_funnels_exceptions_to_on_error() -> None:
    root = _FakeRoot()
    captured: dict[str, Any] = {}

    def target() -> None:
        raise RuntimeError("boom")

    thread = workers.run_in_background(
        target,
        on_done=lambda r: captured.setdefault("result", r),
        on_error=lambda e: captured.setdefault("error", e),
        root=root,
    )
    thread.join(timeout=2)

    while root.calls and "result" not in captured and "error" not in captured:
        _, cb = root.calls.pop(0)
        cb()

    assert isinstance(captured.get("error"), RuntimeError)
    assert str(captured["error"]) == "boom"
    assert "result" not in captured


def test_run_in_background_uses_after_so_main_thread_never_blocks() -> None:
    root = _FakeRoot(max_drains=0)  # do not auto-execute callbacks
    workers.run_in_background(
        lambda: 42,
        on_done=lambda r: None,
        on_error=lambda e: None,
        root=root,
    )
    # The first call to root.after must have been scheduled (proof the worker
    # uses root.after rather than blocking the main thread).
    assert root.calls, "run_in_background must schedule at least one root.after"
    assert root.calls[0][0] > 0, "drain interval must be positive"

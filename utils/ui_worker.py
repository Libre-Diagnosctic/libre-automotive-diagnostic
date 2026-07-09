"""Run blocking work off the Tk main thread and marshal results back safely.

Tkinter is **not thread-safe**: widgets may only be touched from the thread that
runs ``mainloop()``. The bug pattern all over the current GUI is a worker thread
that calls ``label.config(...)`` / ``messagebox`` / creates ``Toplevel`` directly,
which crashes intermittently ("main thread is not in main loop").

:func:`run_async` runs ``work()`` in a background thread, then hands the result
(or the exception) back to the Tk thread via ``root.after(0, ...)`` so every
widget-touching callback executes on the main loop.

``root`` is duck-typed (anything with ``after(delay, callback)``), so this is
unit-testable without a real Tk display.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional


def run_async(
    root,
    work: Callable[[], object],
    *,
    on_success: Optional[Callable[[object], None]] = None,
    on_error: Optional[Callable[[BaseException], None]] = None,
    on_done: Optional[Callable[[], None]] = None,
) -> threading.Thread:
    """Run ``work()`` in a daemon thread; deliver callbacks on the Tk thread.

    Exactly one of ``on_success`` / ``on_error`` fires per run; ``on_done`` always
    fires last (success or failure). All three are dispatched via ``root.after``.
    Returns the started thread (handy for tests).
    """

    def worker() -> None:
        try:
            result = work()
        except BaseException as exc:  # noqa: BLE001 - re-raised to the Tk thread
            if on_error is not None:
                root.after(0, lambda e=exc: on_error(e))
        else:
            if on_success is not None:
                root.after(0, lambda r=result: on_success(r))
        finally:
            if on_done is not None:
                root.after(0, on_done)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread


class TkSpinner:
    """A Braille spinner driven entirely on the Tk thread via ``root.after``.

    Replaces the old ``animate_loading`` threads that mutated a label from a
    background thread. Safe against the label being destroyed mid-spin.
    """

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, root, label, task_name: str = "Working", interval_ms: int = 100):
        self._root = root
        self._label = label
        self._task = task_name
        self._interval = interval_ms
        self._running = False
        self._i = 0

    def start(self) -> None:
        self._running = True
        self._i = 0
        self._tick()

    def _tick(self) -> None:
        if not self._running:
            return
        try:
            if not self._label.winfo_exists():
                return
            frame = self.FRAMES[self._i % len(self.FRAMES)]
            self._label.config(text=f"{self._task}... {frame}")
        except Exception:  # widget went away between check and config
            return
        self._i += 1
        self._root.after(self._interval, self._tick)

    def stop(self, clear: bool = True) -> None:
        self._running = False
        if not clear:
            return
        try:
            if self._label.winfo_exists():
                self._label.config(text="")
        except Exception:
            pass

"""Tests for the Tk thread-marshaling helper — no display required.

A fake root queues ``after`` callbacks instead of scheduling them on a real Tk
loop, so we can assert that results/errors are delivered through ``after`` (i.e.
would run on the main thread) rather than from the worker thread.
"""
from __future__ import annotations

import threading

from utils.ui_worker import TkSpinner, run_async


class QueueRoot:
    """Records ``after`` callbacks; ``run_pending`` plays them back."""

    def __init__(self):
        self._q: list = []
        self._lock = threading.Lock()

    def after(self, _delay, callback, *args):
        with self._lock:
            self._q.append((callback, args))

    def run_pending(self):
        while True:
            with self._lock:
                if not self._q:
                    return
                callback, args = self._q.pop(0)
            callback(*args)


def _boom():
    raise ValueError("boom")


def test_success_delivered_via_after():
    root = QueueRoot()
    got = {}
    t = run_async(root, work=lambda: 42, on_success=lambda r: got.__setitem__("r", r))
    t.join(timeout=2)
    assert "r" not in got          # nothing runs until the Tk loop pumps
    root.run_pending()
    assert got["r"] == 42


def test_error_delivered_via_after():
    root = QueueRoot()
    errs = {}
    t = run_async(root, work=_boom, on_error=lambda e: errs.__setitem__("e", e))
    t.join(timeout=2)
    root.run_pending()
    assert isinstance(errs["e"], ValueError)


def test_on_done_runs_on_success_and_error():
    root = QueueRoot()
    calls = {"n": 0}
    inc = lambda: calls.__setitem__("n", calls["n"] + 1)

    run_async(root, work=lambda: 1, on_done=inc).join(timeout=2)
    run_async(root, work=_boom, on_done=inc).join(timeout=2)
    root.run_pending()
    assert calls["n"] == 2


def test_success_not_called_on_error():
    root = QueueRoot()
    flags = {"ok": False}
    run_async(
        root, work=_boom,
        on_success=lambda r: flags.__setitem__("ok", True),
        on_error=lambda e: None,
    ).join(timeout=2)
    root.run_pending()
    assert flags["ok"] is False


class FakeLabel:
    def __init__(self):
        self.text = None
        self.alive = True

    def winfo_exists(self):
        return self.alive

    def config(self, text=None, **_):
        if text is not None:
            self.text = text


class ManualRoot:
    """``after`` records the next tick without running it (so the spin loop halts)."""

    def __init__(self):
        self.pending = None

    def after(self, _delay, callback, *args):
        self.pending = (callback, args)


def test_spinner_updates_label_and_stops():
    root = ManualRoot()
    label = FakeLabel()
    spin = TkSpinner(root, label, "Scanning")
    spin.start()
    assert label.text.startswith("Scanning...")   # first frame drawn
    spin.stop()
    assert label.text == ""                         # cleared on stop
    # A queued tick after stop() must be a no-op (guards against zombie loops).
    cb, args = root.pending
    cb(*args)
    assert label.text == ""


def test_spinner_survives_destroyed_label():
    root = ManualRoot()
    label = FakeLabel()
    spin = TkSpinner(root, label, "Working")
    label.alive = False
    spin.start()  # must not raise even though the widget is gone

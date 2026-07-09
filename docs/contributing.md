# Contributing

## Dev setup

```bash
git clone <repo> && cd libre-automotive-diagnostic
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt                   # GUI + core
pip install -r requirements-socketcan.txt         # python-can, can-isotp (Linux, optional)
python -m pytest                                  # should be green
```

You do **not** need a car or a CAN adapter to develop or test — see
[vcan-and-testing.md](vcan-and-testing.md).

## Conventions

- **Python 3.10+**, `from __future__ import annotations` at the top of each module.
- Type hints on public functions; module + public-symbol docstrings.
- Match the surrounding style (naming, comment density). These modules read like
  spec references on purpose — keep them that way.
- No `print` in library code (`protocol/`, `transport/`); surface information via
  return values / exceptions / the logger.
- **Protocol code depends only on `transport.base.Transport`** — never import a
  concrete backend or `serial`/`isotp` in `protocol/`.

## Where things go

| Change | Put it in |
|---|---|
| New Mode 01 PID | one `_pid(...)` row in `protocol/pids.py` |
| New/edited DTC definition | the spreadsheet → rerun `scripts/import_dtc_library.py` (don't hand-edit the JSON) |
| New NRC | the `NRC` dict in `protocol/nrc.py` |
| New UDS/KWP service | a method on `UDSClient` / `KWP2000Client` |
| New seed/key algorithm | `protocol/security/algorithms/<Name>.py` (see [security doc](security-access-0x27.md)) |
| New transport medium | a `Transport` subclass in `transport/` |
| New OEM protocol profile | a module in `protocol/` layered on UDS/KWP (see `ford_gds.py`) |

## Adding a feature — the loop

1. **Write the test first**, using `FakeTransport` (or vcan + simulator for
   multi-frame). Assert both the request bytes (`bus.sent`) and the parsed reply.
2. Implement against the `Transport` interface.
3. `python -m pytest` green.
4. If it's user-facing, wire it through `DiagnosticSession` and, if needed, the GUI
   (long calls via `utils/ui_worker.run_async` so the UI thread never blocks).
5. Add/'update the matching doc in `docs/`.

## Safety rules (non-negotiable)

- **Writes to the vehicle are gated, confirmed, and logged.** Clear-DTC, UDS
  0x2E/0x31/0x27, flashing. Never perform a destructive action silently.
- **Never ship a fake seed/key as if it were real.** SecurityAccess algorithms come
  from the ported library or a user-supplied function — not a placeholder.
- **No secrets/PII in logs or commits.** VINs and ECU ids stay local (see the
  project README's privacy section).
- **Credit third-party code.** Anything ported keeps its license + attribution in
  [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

## Threading (GUI)

Tkinter is single-threaded; widgets may only be touched on the main loop. Do slow
work off-thread and marshal results back:

```python
from utils.ui_worker import run_async

run_async(
    self.root,
    work=lambda: session.read_live_data(),      # runs in a background thread
    on_success=lambda data: self.render(data),  # runs on the Tk thread
    on_error=lambda e: self.show_error(e),
    on_done=self.stop_spinner,
)
```

Never call `widget.config(...)`, `messagebox`, or create a `Toplevel` from a worker
thread — that's the intermittent "main thread is not in main loop" crash.

## Commits & PRs

- Branch off `main`; the current integration branch is `feat/socketcan-transport`.
- Conventional-ish messages (`feat(protocol): …`, `fix(gui): …`).
- Keep protocol changes and their tests in the same PR.
- Run `python -m pytest` before pushing.

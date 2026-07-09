# Archived: C "HardwareSocketCAN" prototype

This tree is kept for reference only. **It does not compile or link** and is not
part of the build. It was an early, ambitious sketch of a standalone C VCI
gateway ("K-OBD-Pi"); the project's diagnostic core has since moved to the
Python SocketCAN + ISO-TP stack (see [`../../SOCKETCAN.md`](../../SOCKETCAN.md)).

## Why it was archived

Concrete, verifiable problems (not stylistic):

- **Missing headers.** Core engines `#include "../../lib/uds_iso14229.h"`,
  `crypto_auth.h`, and `iso_tp_stack.h`, none of which exist in the repo.
- **Inconsistent signatures.** `uds_read_data_by_id()` is called with 4 args in
  `immo_keygen.c` but 2 args in `global_scan_engine.c` / `variant_coding.c` —
  proof these files were never compiled together.
- **Undefined link symbols.** `crc32_compute()` is declared `extern` in
  `secure_server.c` but defined nowhere; `main.c` links `web_server_run`,
  `health_monitor_run`, and `dashboard_render_run`, none of which the Makefile
  builds (and `dashboard_render_run` is defined nowhere).
- **Wrong Makefile paths.** It compiles `lib/obd_formulas.c` (actually under
  `src/core/`) and `lib/iso_tp_stack.c` (does not exist).
- **Security theater in the gateway.** `secure_server.c` advertises "TLS 1.3"
  but never loads a certificate/key (so `SSL_accept` fails on every connection),
  and `web_server.c` binds port 80 on `INADDR_ANY` with no auth and CORS `*`.
- **Dangerous placeholder crypto.** `security_unlock.c` ships a toy seed→key
  algorithm (`seed ^ 0xACE0BADE`, rotate, add) with no attempt-counter awareness
  — running it against a real ECU risks tripping SecurityAccess lockout.

## If you want to revive any of it

The useful, correct part was `src/core/obd_formulas.c` (the J1979 math); those
formulas now live, verified by tests, in `protocol/pids.py`. Anything else should
be rebuilt on the Python stack, or — if a native VCI is genuinely needed later —
started fresh on the kernel `can_isotp` module rather than a hand-rolled ISO-TP.

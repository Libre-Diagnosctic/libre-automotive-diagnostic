# Third-Party Notices

This project incorporates third-party open-source components. Each remains subject
to its own license.

## UnlockECU — ECU SecurityAccess (0x27) seed/key algorithms

- **Upstream:** https://github.com/jglim/UnlockECU
- **Author:** JinGen Lim (jglim)
- **License:** MIT — Copyright (c) 2020 JinGen Lim
- **Full license text:** [`protocol/security/UNLOCKECU_LICENSE.txt`](protocol/security/UNLOCKECU_LICENSE.txt)

The Python package [`protocol/security/`](protocol/security/) is a faithful port of
UnlockECU's `SecurityProvider` infrastructure and its seed/key algorithm set, and
[`assets/unlockecu_db.json`](assets/unlockecu_db.json) is the upstream `db.json`
included verbatim. Per the upstream project's own statement, these security functions
and definitions are **reverse-engineered and re-implemented** and contain no
copyrighted or proprietary binary files.

Full credit for the original reverse-engineering and implementation goes to jglim.
This port exists to make those algorithms usable from the Python diagnostic stack;
it does not claim authorship of the underlying algorithms.

### Intended use

SecurityAccess unlocking is provided for **legitimate diagnostics, repair, and
research on vehicles you own or are authorized to service**. Follow the repository's
overall disclaimer of liability.

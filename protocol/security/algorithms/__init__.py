"""Ported UnlockECU seed/key algorithms.

Each module defines one or more :class:`~protocol.security.provider.SecurityProvider`
subclasses (``NAME`` = the db.json ``Provider`` string). The registry imports every
module here and collects the subclasses, so adding an algorithm is just dropping a
new file in this package — no manual registration.

Faithful Python ports of https://github.com/jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).
"""

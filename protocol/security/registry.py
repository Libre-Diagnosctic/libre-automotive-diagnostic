"""Provider registry — discovers every ported seed/key algorithm by name.

Mirrors UnlockECU's reflection-based ``GetSecurityProviders``: it imports every
module in :mod:`protocol.security.algorithms` and collects all
:class:`~protocol.security.provider.SecurityProvider` subclasses, keyed by their
``NAME`` (the ``Provider`` string used in db.json).
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Dict, List, Optional

from .provider import SecurityProvider

_REGISTRY: Optional[Dict[str, SecurityProvider]] = None


def _discover() -> Dict[str, SecurityProvider]:
    from . import algorithms  # local import so an empty package is tolerated

    for mod in pkgutil.iter_modules(algorithms.__path__):
        importlib.import_module(f"{algorithms.__name__}.{mod.name}")

    providers: Dict[str, SecurityProvider] = {}

    def _walk(cls: type) -> None:
        for sub in cls.__subclasses__():
            if sub.NAME and sub.NAME != "SecurityProvider":
                providers.setdefault(sub.NAME, sub())
            _walk(sub)

    _walk(SecurityProvider)
    return providers


def get_providers() -> Dict[str, SecurityProvider]:
    """Return ``{provider_name: instance}`` for every registered algorithm."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _discover()
    return _REGISTRY


def get_provider(name: str) -> Optional[SecurityProvider]:
    return get_providers().get(name)


def provider_names() -> List[str]:
    return sorted(get_providers())

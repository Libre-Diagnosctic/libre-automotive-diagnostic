"""ISO 14229 / KWP2000 SecurityAccess (0x27) unlocking via ported algorithms.

Two layers:
  * :func:`compute_key` — pure ``seed -> key`` for a named ECU + level, using the
    ported provider registry and db.json parameters. Deterministic and testable
    (verified against the UnlockECU IC204 reference vectors).
  * :func:`unlock` — the full 0x27 handshake over a UDS/KWP client: request seed,
    compute key, send key.

Ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim). See db.json attribution.
"""
from __future__ import annotations

from typing import Optional

from .definitions import Definition, find_definition
from .registry import get_provider


class UnlockError(Exception):
    """No definition/provider for the requested ECU, or key generation failed."""


def compute_key(ecu_name: str, access_level: int, seed: bytes,
                definition: Optional[Definition] = None) -> bytes:
    """Compute the 0x27 key for ``seed`` given an ECU name and access level.

    Raises :class:`UnlockError` if the ECU/level is unknown, the provider is not
    registered, or the algorithm rejects the seed.
    """
    d = definition or find_definition(ecu_name, access_level)
    if d is None:
        raise UnlockError(f"No definition for ECU {ecu_name!r} at level {access_level}")
    provider = get_provider(d.provider)
    if provider is None:
        raise UnlockError(f"Provider {d.provider!r} is not registered (ECU {ecu_name!r})")
    key = provider.generate_key(bytes(seed), d.key_length, access_level, d.parameters)
    if key is None:
        raise UnlockError(
            f"{d.provider} rejected seed for {ecu_name!r} level {access_level} "
            f"(seed {seed.hex().upper()})"
        )
    return bytes(key)


def unlock(client, ecu_name: str, access_level: int) -> bool:
    """Run the full SecurityAccess handshake on a UDS/KWP client.

    ``client`` must expose ``security_access_request_seed(level)`` and
    ``security_access_send_key(level, key)`` (see
    :class:`protocol.uds.UDSClient`). Returns True on success. An all-zero seed
    means the ECU is already unlocked, so no key is sent.
    """
    seed = client.security_access_request_seed(access_level)
    if not any(seed):  # all-zero seed => already unlocked
        return True
    key = compute_key(ecu_name, access_level, seed)
    client.security_access_send_key(access_level, key)
    return True

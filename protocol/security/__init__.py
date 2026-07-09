"""ECU SecurityAccess (UDS/KWP 0x27) seed/key algorithms.

A Python port of jglim/UnlockECU (https://github.com/jglim/UnlockECU, MIT,
(c) 2020 JinGen Lim). Full credit to the original author; the seed/key algorithms
and ``db.json`` are reverse-engineered and contain no proprietary blobs.

    from protocol.security import compute_key, unlock, provider_names, ecu_names

    key = compute_key("IC204_2049022600", 9, bytes.fromhex("1122334455667788"))

    # over a live UDS client:
    from protocol.uds import UDSClient
    unlock(UDSClient(transport), "IC204_2049022600", 9)
"""
from .definitions import Definition, ecu_names, find_definition, load_definitions
from .provider import Parameter, SecurityProvider
from .registry import get_provider, get_providers, provider_names
from .unlock import UnlockError, compute_key, unlock

__all__ = [
    "SecurityProvider", "Parameter",
    "Definition", "find_definition", "load_definitions", "ecu_names",
    "get_provider", "get_providers", "provider_names",
    "compute_key", "unlock", "UnlockError",
]

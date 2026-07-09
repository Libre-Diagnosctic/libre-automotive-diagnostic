"""OBD-II / UDS / KWP2000 protocol layer.

Sits on top of a transport backend and speaks in vehicle terms:

    from protocol.obd2 import J1979            # all 10 OBD-II modes (SAE J1979)
    from protocol.uds import UDSClient          # full ISO 14229 service set
    from protocol.kwp2000 import KWP2000Client  # ISO 14230-3 (KWP2000)
    from protocol.ford_gds import FordGDS       # Ford CAN GDS (KWP2000 profile)
    from protocol.dtc_library import describe    # DTC definitions
    from protocol.vin import decode_vin          # VIN -> VinInfo
    from protocol import nrc                      # 0x7F negative-response codes
    from protocol.security import compute_key, unlock  # SecurityAccess 0x27
"""
from . import (  # noqa: F401
    dtc, dtc_library, ford_gds, kwp2000, nrc, obd2, pids, security, uds, vin,
)

__all__ = [
    "dtc", "dtc_library", "ford_gds", "kwp2000", "nrc",
    "obd2", "pids", "security", "uds", "vin",
]

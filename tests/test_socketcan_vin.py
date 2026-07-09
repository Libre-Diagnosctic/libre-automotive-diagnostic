"""Integration test: VIN + DTCs over real ISO-TP on a virtual CAN bus.

This is the keystone test — it proves the full SocketCAN + kernel ISO-TP path,
including multi-frame reassembly (the VIN reply spans several CAN frames).

It is skipped automatically unless running on Linux with ``can-isotp`` installed
and a ``vcan0`` interface up, so the suite stays green on Windows/macOS. On Linux
CI, bring the bus up first:

    sudo modprobe vcan can_isotp
    sudo ip link add dev vcan0 type vcan
    sudo ip link set up vcan0
"""
from __future__ import annotations

import pytest

# Skip the whole module if the can-isotp Python package isn't importable.
pytest.importorskip("isotp")

CHANNEL = "vcan0"


def _vcan_available(channel: str) -> bool:
    """True only on Linux with the given (v)can interface actually up."""
    import socket

    if not hasattr(socket, "AF_CAN"):
        return False
    try:
        s = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    except (AttributeError, OSError):
        return False
    try:
        s.bind((channel,))
        return True
    except OSError:
        return False
    finally:
        s.close()


pytestmark = pytest.mark.skipif(
    not _vcan_available(CHANNEL),
    reason=f"{CHANNEL} unavailable (need Linux with vcan up; see module docstring)",
)


@pytest.fixture
def ecu():
    from simulator.ecu_sim import SimulatedEcu

    sim = SimulatedEcu(CHANNEL).start()
    try:
        yield sim
    finally:
        sim.stop()


def test_read_vin_over_isotp(ecu):
    from protocol.obd2 import read_vin
    from simulator.ecu_sim import DEFAULT_VIN
    from transport.socketcan import SocketCanTransport

    with SocketCanTransport(CHANNEL, ecu=0) as t:
        assert read_vin(t) == DEFAULT_VIN


def test_read_dtcs_over_isotp(ecu):
    from protocol.obd2 import read_dtcs
    from transport.socketcan import SocketCanTransport

    with SocketCanTransport(CHANNEL, ecu=0) as t:
        assert set(read_dtcs(t)) == {"P0301", "P0420"}

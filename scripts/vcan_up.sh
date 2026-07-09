#!/usr/bin/env bash
# Bring up a virtual CAN bus for hardware-free development and CI.
#
# Usage:  ./scripts/vcan_up.sh [interface]   (default: vcan0)
#
# After this you can:
#   python -m simulator.ecu_sim        # serve a virtual ECU
#   candump vcan0                      # watch traffic (from can-utils)
#   pytest tests/test_socketcan_vin.py # run the keystone integration test
set -euo pipefail

IFACE="${1:-vcan0}"

sudo modprobe vcan
sudo modprobe can_isotp
if ! ip link show "$IFACE" >/dev/null 2>&1; then
    sudo ip link add dev "$IFACE" type vcan
fi
sudo ip link set up "$IFACE"

echo "[vcan_up] $IFACE is up."

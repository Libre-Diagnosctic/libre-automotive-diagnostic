#!/bin/bash
# ============================================================================
#  K-OBD-PI AUTOMOTIVE - Hardware bring-up and gateway start script
#  Brings up the SocketCAN interface, loads the kernel module and
#  launches the master orchestrator.
# ============================================================================

set -e

CAN_IFACE="${CAN_IFACE:-can0}"
BITRATE="${BITRATE:-500000}"
APP_BIN="${APP_BIN:-./obd_app}"

echo "[START] Bringing up CAN interface ${CAN_IFACE} @ ${BITRATE} bit/s"
sudo ip link set "${CAN_IFACE}" down 2>/dev/null || true
sudo ip link set "${CAN_IFACE}" up type can bitrate "${BITRATE}" dbitrate "${BITRATE}" fd on 2>/dev/null \
    || sudo ip link set "${CAN_IFACE}" up type can bitrate "${BITRATE}"

echo "[START] Loading kernel driver"
if lsmod | grep -q obd_driver; then
    sudo rmmod obd_driver
fi
sudo insmod driver/obd_driver.ko 2>/dev/null || echo "[START] Driver insert skipped (or built-in)."

echo "[START] Creating device nodes"
MAJOR_VCI=$(grep obd_vci /proc/devices | awk '{print $1}')
MAJOR_DATA=$(grep obd_data /proc/devices | awk '{print $1}')
if [ -n "$MAJOR_VCI" ]; then
    sudo mknod -m 666 /dev/obd_vci c "$MAJOR_VCI" 0 2>/dev/null || true
fi
if [ -n "$MAJOR_DATA" ]; then
    sudo mknod -m 666 /dev/obd_data c "$MAJOR_DATA" 0 2>/dev/null || true
fi

echo "[START] Launching gateway ${APP_BIN}"
exec "$APP_BIN"

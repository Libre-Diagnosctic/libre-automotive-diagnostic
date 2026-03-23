# Libre Automotive Diagnostic - SocketCAN Bridge

A professional Linux Kernel Module (LKM) and user-space toolset for high-performance OBD-II diagnostics on Raspberry Pi.

## Architecture
- **driver/**: Kernel-space CAN frame interceptor and IOCTL bridge.
- **lib/**: ISO-TP (ISO 15765-2) transport layer implementation.
- **src/**: User-space telemetry engine and CLI.
- **scripts/**: Hardware initialization and automation.

## Hardware Requirements
- Raspberry Pi (all versions)
- MCP2515 CAN Controller
- MCP2551/TJA1050 Transceiver

## Quick Start
```bash
chmod +x scripts/start_obd.sh
sudo ./scripts/start_obd.sh

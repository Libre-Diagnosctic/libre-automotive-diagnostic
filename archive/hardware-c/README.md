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

# Hardware SocketCAN Implementation
This sub-module provides a low-level interface to the vehicle's CAN bus using the Linux SocketCAN stack.

## Goal
Implement basic CAN interface to read raw vehicle frames.

## Usage
1. Bring up the interface:
   `sudo ip link set can0 up type can bitrate 500000`
2. Compile:
   `make`
3. Run:
   `./can_raw_receiver`

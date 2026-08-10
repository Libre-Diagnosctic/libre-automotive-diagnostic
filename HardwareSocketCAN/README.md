# Libre Automotive Diagnostic - SocketCAN Bridge

A professional Linux Kernel Module (LKM) and user-space toolset for high-performance OBD-II diagnostics on Raspberry Pi.

## Architecture
- **driver/**: Kernel-space CAN frame interceptor and IOCTL bridge (`/dev/obd_vci` + legacy `/dev/obd_data`), CAN-FD support.
- **lib/**: Protocol stacks and supporting libraries:
  - `iso_tp_stack` / `uds_iso14229` - ISO 15765-2 transport + ISO 14229-1 UDS
  - `doip_iso13400` - ISO 13400-2 Diagnostics over IP
  - `wwh_obd_stack` - ISO 27145 WWH-OBD
  - `j1939_stack` / `dbc_parser` - SAE J1939 + Vector DBC decoding
  - `obd_dtc_decoder` / `uds_did_db` / `obd_pids_db` / `obd_formulas` / `vin_decoder`
  - `websocket_server` (RFC 6455), `mqtt_client` (MQTT 3.1.1)
  - `can_recorder` / `can_replay` / `can_stats` - capture, replay and bus metrics
  - `sgw_policy_engine` - security gateway access control
  - `csv_exporter` / `trip_logger` - data export and trip logging
  - `config_loader` / `logging` / `daemon_utils` / `watchdog` / `self_test`
  - `crypto_auth` / `token_auth_mgr` / `crc_provider` - security and integrity
  - `j2534_runtime` / `vehicle_profiles` - pass-thru runtime and VIN-based tuning
- **src/**: User-space telemetry engine and CLI.
  - `src/core` - master orchestrator, scan/telemetry/health engines
  - `src/gateway` - REST/WebSocket web server + TLS 1.3 secure server
  - `src/ui` - dashboard renderer and input manager
  - `src/analysis` - battery health, fuel/trip statistics, graph engine
- **user-app/**: Standalone demo application.
- **scripts/**: Hardware initialization and automation.

## Runtime Modules (all config-driven via `/etc/kobd/obd.conf`)
| Module | Config gate | Default | What it does |
|---|---|---|---|
| Scan engine | `diag.global_scan` | on | periodic ISO-TP ECU enumeration (VIN + DTC count per ECU) |
| DoIP gateway | `doip.enabled` + `doip.host` | off | ISO 13400-2 Ethernet tester relay to CAN |
| Remote bridge | `remote_bridge.host` | off | downlink injection to a remote SocketCAN endpoint |
| Virtual VCI | `remote_vci.enabled` | off | TCP server streaming raw CAN RX (1 client) |
| J2534 server | `j2534.enabled` | off | SAE J2534-1 Pass-Thru API over TCP |
| DTC / readiness | (always) | on | Mode 03 sweep + I/M readiness via Mode 01 PID 01 |
| Battery / graphs | (always) | on | battery-health estimator + RPM/battery graph sampling |
| REST diag writes | `diag.web_access` | off | security unlock / variant coding / adaptation / immo / ECU reset / clear DTC |

## REST API
- `GET /api/telemetry`, `/api/status`, `/api/scan`, `/api/vin`, `/api/trip`, `/api/dids`
- `GET /api/diag/security?level=N` - UDS SecurityAccess unlock
- `GET /api/diag/variant?did=0xF100&offset=N&mask=M&value=V` - variant coding
- `GET /api/diag/adapt?did=N&value=V&size=N` - adaptation
- `GET /api/diag/immo?op=count|auth&table=N|learn` - immobilizer key management
- `GET /api/diag/reset?type=N`, `GET /api/diag/cleardtc`, `GET /api/diag/session?type=N`
- Write operations return `403` unless `diag.web_access = true` (default-deny).

## Hardware Requirements
- Raspberry Pi (all versions)
- MCP2515 CAN Controller
- MCP2551/TJA1050 Transceiver

## Build
```bash
make all            # kernel module + gateway + CLI tools
make module         # only driver/obd_driver.ko (needs kernel headers)
make gateway        # only obd_app
make tools          # obd_cli, can_raw_receiver, obd_user_app
make secure_server  # optional, requires OpenSSL
```

## Quick Start
```bash
chmod +x scripts/start_obd.sh
sudo ./scripts/start_obd.sh
```

## Usage
1. Bring up the interface:
   `sudo ip link set can0 up type can bitrate 500000`
2. Compile:
   `make`
3. Run:
   `./can_raw_receiver`

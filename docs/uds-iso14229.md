# UDS / ISO 14229-1 (`protocol/uds.py`)

A transport-neutral UDS client with **full service coverage** (0x10–0x87). Each
method builds the request PDU, sends it physically addressed to one ECU, awaits
response-pending (0x78) transparently, checks for negative responses, and returns
the parsed positive-response payload.

```python
from transport.socketcan import SocketCanTransport
from protocol.uds import UDSClient, Session, ResetType

with SocketCanTransport("can0", ecu=0) as t:
    uds = UDSClient(t)
    uds.diagnostic_session_control(Session.EXTENDED)     # 0x10
    vin = uds.read_data_by_identifier(0xF190)            # 0x22
    dtcs = uds.read_dtcs_by_status_mask(0xFF)            # 0x19/0x02
```

## Service coverage

| SID | Service | Method |
|---|---|---|
| 0x10 | DiagnosticSessionControl | `diagnostic_session_control(session)` |
| 0x11 | ECUReset | `ecu_reset(reset_type)` |
| 0x14 | ClearDiagnosticInformation | `clear_diagnostic_information(group)` |
| 0x19 | ReadDTCInformation | `read_dtc_information`, `read_dtcs_by_status_mask`, `read_supported_dtcs` |
| 0x22 | ReadDataByIdentifier | `read_data_by_identifier(did)` |
| 0x23 | ReadMemoryByAddress | `read_memory_by_address(addr, size)` |
| 0x24 | ReadScalingDataByIdentifier | `read_scaling_data_by_identifier(did)` |
| 0x27 | SecurityAccess | `security_access_request_seed`, `security_access_send_key` |
| 0x28 | CommunicationControl | `communication_control(...)` |
| 0x29 | Authentication | `authentication(subfn, data)` |
| 0x2A | ReadDataByPeriodicIdentifier | `read_data_by_periodic_identifier(...)` |
| 0x2C | DynamicallyDefineDataIdentifier | `dynamically_define_data_identifier(...)` |
| 0x2E | WriteDataByIdentifier | `write_data_by_identifier(did, data)` |
| 0x2F | InputOutputControlByIdentifier | `io_control_by_identifier(...)` |
| 0x31 | RoutineControl | `routine_control`, `start_routine`, `stop_routine`, `routine_results` |
| 0x34 | RequestDownload | `request_download(addr, size)` → max block length |
| 0x35 | RequestUpload | `request_upload(addr, size)` |
| 0x36 | TransferData | `transfer_data(bsc, data)` |
| 0x37 | RequestTransferExit | `request_transfer_exit(data)` |
| 0x38 | RequestFileTransfer | `request_file_transfer(mode, data)` |
| 0x3D | WriteMemoryByAddress | `write_memory_by_address(addr, data)` |
| 0x3E | TesterPresent | `tester_present()` |
| 0x83 | AccessTimingParameter | `access_timing_parameter(...)` |
| 0x84 | SecuredDataTransmission | `secured_data_transmission(data)` |
| 0x85 | ControlDTCSetting | `control_dtc_setting(setting_type)` |
| 0x86 | ResponseOnEvent | `response_on_event(...)` |
| 0x87 | LinkControl | `link_control(...)` |

Enums provided: `Service`, `Session` (DEFAULT/PROGRAMMING/EXTENDED/SAFETY_SYSTEM),
`ResetType`, `RoutineControlType`, `DtcReportType`, `DtcSettingType`,
`CommunicationControlType`.

## Timing, response-pending, and errors

The client (`__init__(transport, *, p2=1.0, p2_star=5.0, max_pending=10)`) wraps
the core request in `_send`:

- **P2 / P2\*** — the initial wait (`p2`) and the extended wait after a 0x78
  response-pending (`p2_star`).
- **Response-pending (0x78)** — `_await_final` loops, calling `transport.receive()`
  up to `max_pending` times, so `7F <sid> 78 … <real answer>` is handled for you.
- **Negative responses** raise `NegativeResponseError(request_sid, nrc)`, whose
  `.nrc_name` comes from [`protocol/nrc.py`](negative-response-codes.md).
- **Wrong SID** raises `UnexpectedResponseError`; **no answer** raises
  `UdsTimeoutError`.

```python
from protocol.uds import NegativeResponseError

try:
    uds.write_data_by_identifier(0xF190, b"NEWVIN...")
except NegativeResponseError as e:
    print(e.nrc, e.nrc_name)     # e.g. 0x33 securityAccessDenied
```

## Suppress-positive-response

Sub-function services accept `suppress_response=True`, which ORs the
`0x80` suppress bit into the sub-function and skips waiting for a reply — used for
`tester_present(suppress_response=True)` keep-alive.

## DTCs over UDS (0x19)

```python
uds.read_dtcs_by_status_mask(0xFF)   # [{"code": "P0301-00", "status": 0x2F, "flags": {...}}]
uds.read_supported_dtcs()            # 0x19/0x0A
```

`decode_uds_dtc(hi, mid, lo)` renders the 3-byte UDS DTC as `"P0301-00"` (base code
+ fault-type byte); `decode_dtc_status(byte)` expands the status byte into the
named ISO 14229 Annex D flags (`testFailed`, `confirmedDTC`, …).

## SecurityAccess (0x27)

The raw handshake is `security_access_request_seed(level)` /
`security_access_send_key(level, key)`. To actually **compute** the key from the
seed for a known ECU, use the ported algorithm library — see
[security-access-0x27.md](security-access-0x27.md):

```python
from protocol.security import unlock
unlock(uds, "IC204_2049022600", 9)   # request seed → compute key → send key
```

## Programming sequence sketch (flashing)

```python
uds.diagnostic_session_control(Session.PROGRAMMING)     # 0x10 02
unlock(uds, ecu_name, level)                            # 0x27
max_block = uds.request_download(address, size)         # 0x34
bsc = 1
for chunk in chunks(firmware, max_block - 2):
    uds.transfer_data(bsc, chunk)                       # 0x36
    bsc = (bsc + 1) & 0xFF
uds.request_transfer_exit()                             # 0x37
uds.ecu_reset(ResetType.HARD)                           # 0x11
```

> Flashing is destructive. Gate it behind explicit confirmation and log every step.

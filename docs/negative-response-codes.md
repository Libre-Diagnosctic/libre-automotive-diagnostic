# Negative Response Codes (`protocol/nrc.py`)

When an ECU rejects a request it replies `7F <requestSID> <NRC>`. `protocol/nrc.py`
is the **single source of truth** for those 0x7F codes — both the modern ISO 14229-1
table and the legacy KWP2000 / early-UDS block-transfer codes that older ECUs still
emit but current UDS dropped.

```python
from protocol import nrc

nrc.name(0x35)                 # "invalidKey"
nrc.describe(0x78)             # "0x78 requestCorrectlyReceived-ResponsePending (ECU busy, answer to follow)"
nrc.is_response_pending(0x78)  # True
nrc.is_known(0x35)             # True
0x33 in nrc.NRC                # True
```

Both `uds.py` and `kwp2000.py` import `NRC` and `RESPONSE_PENDING` from here, so
there is exactly one table.

## Why the legacy codes matter

Modern ISO 14229-1 reserves 0x74–0x77 and reassigns 0x79. But the KWP2000 era (and
the reference tester this stack's `printerr` came from) used them for block-transfer
errors, and plenty of ECUs in the field still respond with them. Dropping them would
make our tool misreport a real error as "unknown." So we keep both:

| Code | Name | Source |
|---|---|---|
| 0x70 | uploadDownloadNotAccepted | ISO 14229 |
| 0x71 | transferDataSuspended | ISO 14229 |
| 0x72 | generalProgrammingFailure / transferAborted | ISO 14229 |
| 0x73 | wrongBlockSequenceCounter | ISO 14229 |
| 0x74 | illegalByteCountInBlockTransfer | **legacy KWP** |
| 0x75 | illegalByteCountInBlockTransfer | **legacy KWP** |
| 0x76 | reservedByLegacyBlockTransfer | **legacy KWP** |
| 0x77 | reservedByLegacyBlockTransfer | **legacy KWP** |
| 0x78 | requestCorrectlyReceived-ResponsePending | ISO 14229 |
| 0x79 | incorrectByteCountDuringBlockTransfer | **legacy KWP** |

## The full table (highlights)

The table covers general/format errors (0x10–0x14), busy/conditions (0x21–0x26),
security (0x33–0x3A), the certificate/authentication set (0x50–0x5D), programming
& block transfer (0x70–0x79), session/service context (0x7E, 0x7F), and the
condition-based emissions codes (0x81–0x94: rpm/temperature/voltage/speed too
high/low, transmission range, brake/shifter, etc.). See the module for the complete
mapping.

## Response-pending is special

0x78 is **not really an error** — it means "received, still working." The UDS/KWP
clients treat it as a signal to keep waiting (`p2_star`), not a failure. Use
`nrc.is_response_pending(code)` rather than special-casing `0x78` inline.

## Adding / correcting a code

Edit the `NRC` dict in `protocol/nrc.py` (short ISO/legacy name) and, if the short
name isn't self-explanatory, add a friendly line to `_FRIENDLY`. Nothing else needs
to change — every consumer reads from here.

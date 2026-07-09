"""Negative Response Codes (0x7F) — the single source of truth.

A negative response is ``7F <requestSID> <NRC>``. This module carries the full
ISO 14229-1 table *plus* the legacy KWP2000 / early-UDS block-transfer codes
(0x74, 0x75, 0x76, 0x77, 0x79) that later editions of ISO 14229 dropped but that
older ECUs (and the reference tester this port came from) still emit.

    from protocol import nrc
    nrc.name(0x35)       -> "invalidKey"
    nrc.describe(0x78)   -> "0x78 requestCorrectlyReceived-ResponsePending"
    nrc.is_response_pending(0x78) -> True
"""
from __future__ import annotations

RESPONSE_PENDING = 0x78

# Canonical ISO 14229-1 short names (Annex A.1), extended with legacy KWP codes.
NRC: dict[int, str] = {
    0x00: "positiveResponse",
    0x10: "generalReject",
    0x11: "serviceNotSupported",
    0x12: "subFunctionNotSupported",
    0x13: "incorrectMessageLengthOrInvalidFormat",
    0x14: "responseTooLong",
    0x21: "busyRepeatRequest",
    0x22: "conditionsNotCorrect",
    0x24: "requestSequenceError",
    0x25: "noResponseFromSubnetComponent",
    0x26: "failurePreventsExecutionOfRequestedAction",
    0x31: "requestOutOfRange",
    0x33: "securityAccessDenied",
    0x34: "authenticationRequired",
    0x35: "invalidKey",
    0x36: "exceededNumberOfAttempts",
    0x37: "requiredTimeDelayNotExpired",
    0x38: "secureDataTransmissionRequired",
    0x39: "secureDataTransmissionNotAllowed",
    0x3A: "secureDataVerificationFailed",
    0x50: "certificateVerificationFailed-InvalidTimePeriod",
    0x51: "certificateVerificationFailed-InvalidSignature",
    0x52: "certificateVerificationFailed-InvalidChainOfTrust",
    0x53: "certificateVerificationFailed-InvalidType",
    0x54: "certificateVerificationFailed-InvalidFormat",
    0x55: "certificateVerificationFailed-InvalidContent",
    0x56: "certificateVerificationFailed-InvalidScope",
    0x57: "certificateVerificationFailed-InvalidCertificate",
    0x58: "ownershipVerificationFailed",
    0x59: "challengeCalculationFailed",
    0x5A: "settingAccessRightsFailed",
    0x5B: "sessionKeyCreationOrDerivationFailed",
    0x5C: "configurationDataUsageFailed",
    0x5D: "deAuthenticationFailed",
    0x70: "uploadDownloadNotAccepted",
    0x71: "transferDataSuspended",
    0x72: "generalProgrammingFailure",
    0x73: "wrongBlockSequenceCounter",
    # -- legacy KWP2000 / early-UDS block-transfer codes (kept for old ECUs) ----
    0x74: "illegalByteCountInBlockTransfer",       # legacy
    0x75: "illegalByteCountInBlockTransfer",       # legacy (paired with 0x74)
    0x76: "reservedByLegacyBlockTransfer",         # legacy reserved
    0x77: "reservedByLegacyBlockTransfer",         # legacy reserved
    0x78: "requestCorrectlyReceived-ResponsePending",
    0x79: "incorrectByteCountDuringBlockTransfer",  # legacy
    0x7E: "subFunctionNotSupportedInActiveSession",
    0x7F: "serviceNotSupportedInActiveSession",
    0x81: "rpmTooHigh",
    0x82: "rpmTooLow",
    0x83: "engineIsRunning",
    0x84: "engineIsNotRunning",
    0x85: "engineRunTimeTooLow",
    0x86: "temperatureTooHigh",
    0x87: "temperatureTooLow",
    0x88: "vehicleSpeedTooHigh",
    0x89: "vehicleSpeedTooLow",
    0x8A: "throttle/PedalTooHigh",
    0x8B: "throttle/PedalTooLow",
    0x8C: "transmissionRangeNotInNeutral",
    0x8D: "transmissionRangeNotInGear",
    0x8F: "brakeSwitch(es)NotClosed",
    0x90: "shifterLeverNotInPark",
    0x91: "torqueConverterClutchLocked",
    0x92: "voltageTooHigh",
    0x93: "voltageTooLow",
    0x94: "resourceTemporarilyNotAvailable",
}

# A few human-readable descriptions where the short name is not self-evident.
_FRIENDLY: dict[int, str] = {
    0x78: "requestCorrectlyReceived-ResponsePending (ECU busy, answer to follow)",
    0x21: "busyRepeatRequest (ECU busy; retry the request)",
    0x22: "conditionsNotCorrect (preconditions for the service are not met)",
    0x31: "requestOutOfRange (parameter/identifier not supported or out of range)",
    0x33: "securityAccessDenied (unlock required via SecurityAccess 0x27)",
    0x35: "invalidKey (SecurityAccess key was wrong)",
    0x36: "exceededNumberOfAttempts (too many bad keys; ECU locked out)",
    0x37: "requiredTimeDelayNotExpired (wait before retrying SecurityAccess)",
    0x72: "generalProgrammingFailure / transferAborted",
}


def name(code: int) -> str:
    """Short ISO/legacy name for an NRC, or ``"unknownNRC(0xNN)"``."""
    return NRC.get(code, f"unknownNRC(0x{code:02X})")


def describe(code: int) -> str:
    """``"0x35 invalidKey (SecurityAccess key was wrong)"`` style description."""
    return f"0x{code:02X} {_FRIENDLY.get(code, name(code))}"


def is_response_pending(code: int) -> bool:
    return code == RESPONSE_PENDING


def is_known(code: int) -> bool:
    return code in NRC

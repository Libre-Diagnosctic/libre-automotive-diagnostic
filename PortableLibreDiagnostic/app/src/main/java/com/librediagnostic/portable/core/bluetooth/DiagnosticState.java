package com.librediagnostic.portable.core.bluetooth;

/**
 * Architectural enumeration representing the reactive states of the vehicle diagnostic engine.
 * Used by the Presentation layer to safely adapt UI components based on hardware operations.
 */
public enum DiagnosticState {

    /**
     * Hardware layers are completely shut down, sockets are closed, resources released.
     */
    DISCONNECTED(0, "Disconnected"),

    /**
     * Actively performing discovery or opening an RFCOMM serial channel to the OBD-II adapter.
     */
    CONNECTING(1, "Establishing Connection..."),

    /**
     * Physical layer connection open. Initializing ELM327 protocol strings (AT commands).
     */
    INITIALIZING(2, "Initializing OBD Protocol..."),

    /**
     * Hardware channel initialized and ready to dispatch PID queries or DTC extraction requests.
     */
    CONNECTED_READY(3, "System Ready"),

    /**
     * Active streaming state loop. Reading sensor fields or extracting real-time vehicle logs.
     */
    STREAMING(4, "Streaming Live Data"),

    /**
     * An execution exception occurred (e.g., lost packet, device out of range, broken stream).
     */
    ERROR(5, "Diagnostic Failure");

    private final int stateCode;
    private final String userFriendlyLabel;

    DiagnosticState(int stateCode, String userFriendlyLabel) {
        this.stateCode = stateCode;
        this.userFriendlyLabel = userFriendlyLabel;
    }

    public int getStateCode() {
        return stateCode;
    }

    public String getUserFriendlyLabel() {
        return userFriendlyLabel;
    }

    /**
     * Utility assertion check to determine if data transactions are safely possible.
     *
     * @return true if the current state can process read/write automotive commands.
     */
    public boolean isActiveSession() {
        return this == CONNECTED_READY || this == STREAMING;
    }

    /**
     * Operational state check to determine if UI should lock down inputs during long running executions.
     *
     * @return true if hardware links are currently mutating state profiles.
     */
    public boolean isTransitionalState() {
        return this == CONNECTING || this == INITIALIZING;
    }
}

package com.librediagnostic.portable.core.parser;

/**
 * Interface contract defining the execution architecture for all automotive commands.
 * Supports standard OBD-II PIDs and serves as the architectural foundation for
 * brand-specific and manufacturer-defined diagnostic payloads.
 */
public interface ObdCommand {

    /**
     * Retrieves the raw alphanumeric command sequence to be transmitted over the serial interface.
     * Example: "010C" for Engine RPM or "010D" for Vehicle Speed.
     *
     * @return Formatted command string ready for ELM327 transmission.
     */
    String getRawCommand();

    /**
     * Provides a human-readable identifier name for the metric or diagnostic parameter.
     * Example: "Engine RPM" or "Coolant Temperature".
     *
     * @return Descriptive identifier string.
     */
    String getMetricName();

    /**
     * Provides the standard measurement unit notation associated with the final calculated result.
     * Example: "rpm", "km/h", "°C".
     *
     * @return Measurement unit symbol string.
     */
    String getMeasurementUnit();

    /**
     * Executes the specific functional algorithm to decode incoming hex responses from the ECU.
     * Must encapsulate data verification and protection boundaries against structural corruption.
     *
     * @param rawResponse The clean alphanumeric response buffer string received from the vehicle.
     * @return The formatted, user-friendly numerical or structural metric value.
     * @throws IllegalArgumentException If the raw payload cannot be evaluated against standard specs.
     */
    String parseResponse(String rawResponse) throws IllegalArgumentException;
}

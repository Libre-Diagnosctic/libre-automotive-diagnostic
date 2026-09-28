package com.librediagnostic.portable.core.parser;

/**
 * Technical implementation of the Standard OBD-II Service 01 PID 0C (Engine RPM).
 * Implements the standard automotive decoding algorithm: ((A * 256) + B) / 4
 */
public class EngineRpmCommand implements ObdCommand {

    private static final String PID_COMMAND = "010C";
    private static final String METRIC_NAME = "Engine RPM";
    private static final String UNIT_RPM = "rpm";

    @Override
    public String getRawCommand() {
        return PID_COMMAND;
    }

    @Override
    public String getMetricName() {
        return METRIC_NAME;
    }

    @Override
    public String getMeasurementUnit() {
        return UNIT_RPM;
    }

    @Override
    public String parseResponse(String rawResponse) throws IllegalArgumentException {
        if (rawResponse == null || rawResponse.trim().isEmpty()) {
            throw new IllegalArgumentException("Response stream buffer cannot be null or empty.");
        }

        String cleanPayload = rawResponse.replaceAll("\\s+", "").toUpperCase();

        if (cleanPayload.contains("NODATA") || cleanPayload.contains("ERROR") || cleanPayload.contains("STOPPED")) {
            return "0";
        }

        if (cleanPayload.length() >= 8 && cleanPayload.startsWith("410C")) {
            try {
                int byteA = Integer.parseInt(cleanPayload.substring(4, 6), 16);
                int byteB = Integer.parseInt(cleanPayload.substring(6, 8), 16);

                int calculatedRpm = ((byteA * 256) + byteB) / 4;
                return String.valueOf(calculatedRpm);

            } catch (NumberFormatException e) {
                throw new IllegalArgumentException("Corrupted bitstream parsing signature.", e);
            }
        }

        return "0";
    }
}

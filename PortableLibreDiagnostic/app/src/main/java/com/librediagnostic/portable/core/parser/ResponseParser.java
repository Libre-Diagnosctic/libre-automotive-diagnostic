package com.librediagnostic.portable.core.parser;

import java.util.HashMap;
import java.util.Map;

/**
 * Central multiplexer responsible for cleansing raw ECU buffers, validating
 * diagnostic responses, and routing payloads to target command parsers.
 */
public class ResponseParser {

    private final Map<String, ObdCommand> commandRegistry;

    public ResponseParser() {
        this.commandRegistry = new HashMap<>();
        registerDefaultCommands();
    }

    private void registerDefaultCommands() {
        ObdCommand rpm = new EngineRpmCommand();
        commandRegistry.put(rpm.getRawCommand(), rpm);
    }

    public String sanitize(String rawInput) {
        if (rawInput == null) {
            return "";
        }
        return rawInput.replaceAll("\\s+", "")
                .replaceAll(">+", "")
                .replaceAll("\\r", "")
                .replaceAll("\\n", "")
                .toUpperCase();
    }

    public boolean isErrorFrame(String sanitizedPayload) {
        if (sanitizedPayload == null || sanitizedPayload.isEmpty()) {
            return true;
        }
        return sanitizedPayload.contains("NODATA") ||
                sanitizedPayload.contains("ERROR") ||
                sanitizedPayload.contains("STOPPED") ||
                sanitizedPayload.contains("UNABLETOCONNECT") ||
                sanitizedPayload.contains("BUSINITERROR");
    }

    public String dispatchAndParse(String commandId, String rawResponse) {
        String cleanPayload = sanitize(rawResponse);

        if (isErrorFrame(cleanPayload)) {
            return "0";
        }

        ObdCommand targetCommand = commandRegistry.get(commandId);
        if (targetCommand != null) {
            try {
                return targetCommand.parseResponse(rawResponse);
            } catch (IllegalArgumentException e) {
                return "0";
            }
        }
        return "0";
    }
}

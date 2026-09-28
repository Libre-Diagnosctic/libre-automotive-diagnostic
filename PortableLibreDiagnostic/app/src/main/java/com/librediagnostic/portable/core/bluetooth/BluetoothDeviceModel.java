package com.librediagnostic.portable.core.bluetooth;

import java.util.Objects;

/**
 * Core domain entity wrapping hardware specifications for discovered
 * and paired ELM327 Bluetooth/OBD-II vehicle adapters.
 */
public class BluetoothDeviceModel {

    private final String name;
    private final String macAddress;
    private final boolean isPaired;
    private final int rssi;

    public BluetoothDeviceModel(String name, String macAddress, boolean isPaired, int rssi) {
        this.name = (name == null || name.isEmpty()) ? "Unknown OBD Adapter" : name;
        this.macAddress = (macAddress == null) ? "00:00:00:00:00:00" : macAddress;
        this.isPaired = isPaired;
        this.rssi = rssi;
    }

    public String getName() {
        return name;
    }

    public String getMacAddress() {
        return macAddress;
    }

    public boolean isPaired() {
        return isPaired;
    }

    public int getRssi() {
        return rssi;
    }

    /**
     * Asserts structural syntax validity against standard hardware MAC regex guidelines.
     */
    public boolean isValidMacAddress() {
        if (macAddress == null) return false;
        String macRegex = "^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$";
        return macAddress.matches(macRegex);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        BluetoothDeviceModel that = (BluetoothDeviceModel) o;
        return Objects.equals(macAddress, that.macAddress);
    }

    @Override
    public int hashCode() {
        return Objects.hash(macAddress);
    }

    @Override
    public String toString() {
        return name + " [" + macAddress + "]" + (isPaired ? " (Paired)" : " (Discovered)") + " RSSI: " + rssi + "dBm";
    }
}

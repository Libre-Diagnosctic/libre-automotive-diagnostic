package com.librediagnostic.portable.core.bluetooth;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Core hardware manager handling safe multi-threaded RFCOMM socket connections,
 * data streams, and lifecycle operations with ELM327 Bluetooth adapters.
 */
public class BluetoothManager {

    private static final UUID SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");

    private final BluetoothAdapter bluetoothAdapter;
    private final ExecutorService threadPool;

    private BluetoothSocket socket;
    private InputStream inputStream;
    private OutputStream outputStream;
    private boolean isConnecting = false;

    public BluetoothManager() {
        this.bluetoothAdapter = BluetoothAdapter.getDefaultAdapter();
        this.threadPool = Executors.newFixedThreadPool(2);
    }

    public boolean isBluetoothEnabled() {
        return bluetoothAdapter != null && bluetoothAdapter.isEnabled();
    }

    @SuppressLint("MissingPermission")
    public synchronized void connect(String macAddress, ConnectionCallback callback) {
        if (isConnecting || isConnected()) {
            callback.onFailure(new IllegalStateException("Connection process active or already established."));
            return;
        }

        if (!isBluetoothEnabled()) {
            callback.onFailure(new IOException("Bluetooth hardware is powered off."));
            return;
        }

        isConnecting = true;

        threadPool.execute(() -> {
            try {
                if (bluetoothAdapter.isDiscovering()) {
                    bluetoothAdapter.cancelDiscovery();
                }

                BluetoothDevice device = bluetoothAdapter.getRemoteDevice(macAddress);
                socket = device.createRfcommSocketToServiceRecord(SPP_UUID);
                socket.connect();

                inputStream = socket.getInputStream();
                outputStream = socket.getOutputStream();

                synchronized (BluetoothManager.this) {
                    isConnecting = false;
                }
                callback.onSuccess();

            } catch (IOException e) {
                synchronized (BluetoothManager.this) {
                    isConnecting = false;
                    disconnect();
                }
                callback.onFailure(e);
            }
        });
    }

    public synchronized boolean isConnected() {
        return socket != null && socket.isConnected() && inputStream != null && outputStream != null;
    }

    public synchronized void disconnect() {
        try {
            if (inputStream != null) inputStream.close();
            if (outputStream != null) outputStream.close();
            if (socket != null) socket.close();
        } catch (IOException ignored) {
            // Ignored during forceful cleanup sequence
        } finally {
            inputStream = null;
            outputStream = null;
            socket = null;
            isConnecting = false;
        }
    }

    public InputStream getInputStream() {
        return inputStream;
    }

    public OutputStream getOutputStream() {
        return outputStream;
    }

    public interface ConnectionCallback {
        void onSuccess();
        void onFailure(Throwable throwable);
    }
}

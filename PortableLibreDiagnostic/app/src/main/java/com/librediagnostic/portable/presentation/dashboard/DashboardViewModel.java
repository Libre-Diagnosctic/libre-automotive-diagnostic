package com.librediagnostic.portable.presentation.dashboard;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.ViewModel;
import com.librediagnostic.portable.core.bluetooth.BluetoothManager;
import com.librediagnostic.portable.core.bluetooth.DiagnosticState;
import com.librediagnostic.portable.core.parser.EngineRpmCommand;
import com.librediagnostic.portable.core.parser.ObdCommand;
import com.librediagnostic.portable.core.parser.ResponseParser;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Architectural StateHolder responsible for coordinating background execution loops,
 * managing telemetry schedules, and exposing reactive UI streams.
 */
public class DashboardViewModel extends ViewModel {

    private final MutableLiveData<DiagnosticState> uiState = new MutableLiveData<>(DiagnosticState.DISCONNECTED);
    private final MutableLiveData<String> rpmTelemetry = new MutableLiveData<>("0");

    private final BluetoothManager bluetoothManager;
    private final ResponseParser responseParser;
    private final ObdCommand rpmCommand;
    private ScheduledExecutorService scheduler;

    public DashboardViewModel() {
        this.bluetoothManager = new BluetoothManager();
        this.responseParser = new ResponseParser();
        this.rpmCommand = new EngineRpmCommand();
    }

    public LiveData<DiagnosticState> getUiState() {
        return uiState;
    }

    public LiveData<String> getRpmTelemetry() {
        return rpmTelemetry;
    }

    public void establishVehicleSession(String macAddress) {
        uiState.setValue(DiagnosticState.CONNECTING);

        bluetoothManager.connect(macAddress, new BluetoothManager.ConnectionCallback() {
            @Override
            public void onSuccess() {
                uiState.postValue(DiagnosticState.CONNECTED_READY);
                startTelemetryStreamLoop();
            }

            @Override
            public void onFailure(Throwable throwable) {
                uiState.postValue(DiagnosticState.ERROR);
                rpmTelemetry.postValue("0");
            }
        });
    }

    private void startTelemetryStreamLoop() {
        uiState.postValue(DiagnosticState.STREAMING);
        scheduler = Executors.newSingleThreadScheduledExecutor();

        scheduler.scheduleAtFixedRate(() -> {
            if (!bluetoothManager.isConnected()) {
                handleSessionFailure();
                return;
            }

            try {
                OutputStream out = bluetoothManager.getOutputStream();
                InputStream in = bluetoothManager.getInputStream();

                out.write((rpmCommand.getRawCommand() + "\r").getBytes());
                out.flush();

                byte[] buffer = new byte[1024];
                int bytesRead = in.read(buffer);
                if (bytesRead > 0) {
                    String rawString = new String(buffer, 0, bytesRead);
                    String parsedResult = responseParser.dispatchAndParse(rpmCommand.getRawCommand(), rawString);
                    rpmTelemetry.postValue(parsedResult);
                }
            } catch (Exception e) {
                handleSessionFailure();
            }
        }, 0, 100, TimeUnit.MILLISECONDS);
    }

    private void handleSessionFailure() {
        bluetoothManager.disconnect();
        uiState.postValue(DiagnosticState.ERROR);
        rpmTelemetry.postValue("0");
        stopTelemetryStreamLoop();
    }

    private void stopTelemetryStreamLoop() {
        if (scheduler != null && !scheduler.isShutdown()) {
            scheduler.shutdown();
        }
    }

    @Override
    protected void onCleared() {
        super.onCleared();
        stopTelemetryStreamLoop();
        bluetoothManager.disconnect();
    }
}

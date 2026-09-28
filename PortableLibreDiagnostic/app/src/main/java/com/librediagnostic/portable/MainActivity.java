package com.librediagnostic.portable.presentation.dashboard;

import android.os.Bundle;
import android.view.View;
import android.widget.ProgressBar;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import androidx.lifecycle.ViewModelProvider;
import com.librediagnostic.portable.core.bluetooth.DiagnosticState;

/**
 * Main Presentation view controller enforcing Android lifecycle boundaries
 * and subscribing to reactive telemetry changes.
 */
public class MainActivity extends AppCompatActivity {

    private DashboardViewModel viewModel;
    private TextView tvStatus;
    private TextView tvRpmValue;
    private ProgressBar loadingIndicator;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setupViewLayouts();

        viewModel = new ViewModelProvider(this).get(DashboardViewModel.class);

        viewModel.getUiState().observe(this, this::renderUiState);
        viewModel.getRpmTelemetry().observe(this, rpm -> tvRpmValue.setText(rpm));

        viewModel.establishVehicleSession("00:11:22:33:44:55");
    }

    private void renderUiState(DiagnosticState state) {
        if (state == null) return;

        tvStatus.setText("System Connection Profile: " + state.getUserFriendlyLabel());

        switch (state) {
            case CONNECTING:
            case INITIALIZING:
                loadingIndicator.setVisibility(View.VISIBLE);
                break;
            case CONNECTED_READY:
            case STREAMING:
                loadingIndicator.setVisibility(View.GONE);
                break;
            case DISCONNECTED:
            case ERROR:
            default:
                loadingIndicator.setVisibility(View.GONE);
                break;
        }
    }

    private void setupViewLayouts() {
        tvStatus = new TextView(this);
        tvRpmValue = new TextView(this);
        loadingIndicator = new ProgressBar(this, null, android.R.attr.progressBarStyleLarge);

        setContentView(tvStatus);
    }
}

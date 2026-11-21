package com.areole.dpc;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.admin.DevicePolicyManager;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * MainActivity — On-Device Owner Console & Non-Destructive Unenrollment UI
 *
 * Notice we build the entire layout programmatically with standard Android views
 * so zero third-party XML layout/Material dependencies or bloat libraries are
 * needed during compilation. While open in the foreground, it polls your
 * self-hosted server every 15 seconds for queued commands (debloat, notification
 * mute, app hide/unhide, optional Thingino install, or clean deprovision).
 */
public class MainActivity extends Activity {
    private static final int REQ_PROVISION_WP = 4101;
    private TextView statusView;
    private EditText serverInput;
    private EditText userInput;
    private ScheduledExecutorService poller;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.parseColor("#0F172A"));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(40, 56, 40, 56);
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("Areole Provisioner DPC");
        title.setTextColor(Color.parseColor("#F8FAFC"));
        title.setTextSize(22f);
        title.setTypeface(null, Typeface.BOLD);
        root.addView(title);

        statusView = new TextView(this);
        statusView.setTextColor(Color.parseColor("#CBD5E1"));
        statusView.setTextSize(14f);
        statusView.setPadding(0, 20, 0, 28);
        root.addView(statusView);

        serverInput = new EditText(this);
        serverInput.setHint("Provision Server URL (e.g. http://192.0.2.10:8780)");
        serverInput.setTextColor(Color.WHITE);
        serverInput.setHintTextColor(Color.parseColor("#64748B"));
        serverInput.setText(DpcConfig.prefs(this).getString(DpcConfig.KEY_SERVER_URL, ""));
        root.addView(serverInput);

        userInput = new EditText(this);
        userInput.setHint("Profile Label (default: Owner)");
        userInput.setTextColor(Color.WHITE);
        userInput.setHintTextColor(Color.parseColor("#64748B"));
        userInput.setText(DpcConfig.prefs(this).getString(DpcConfig.KEY_USERNAME, "Owner"));
        root.addView(userInput);

        root.addView(makeBtn("Save Config & Sync Server", "#2563EB", v -> {
            DpcConfig.prefs(this).edit()
                .putString(DpcConfig.KEY_SERVER_URL, serverInput.getText().toString().trim())
                .putString(DpcConfig.KEY_USERNAME, userInput.getText().toString().trim())
                .apply();
            DpcConfig.applyZeroRestrictionsAndLabel(this);
            runAsyncSync();
        }));

        // Optional BYOD Work Profile trigger for phones already past first-boot setup
        root.addView(makeBtn("Create Unrestricted Work Profile (BYOD)", "#0D9488", v -> {
            Intent p = new Intent(DevicePolicyManager.ACTION_PROVISION_MANAGED_PROFILE);
            p.putExtra(DevicePolicyManager.EXTRA_PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME,
                DpcConfig.adminComponent(this));
            try {
                startActivityForResult(p, REQ_PROVISION_WP);
            } catch (Throwable t) {
                Toast.makeText(this, "Provision launch failed: " + t.getMessage(), Toast.LENGTH_LONG).show();
            }
        }));

        root.addView(makeBtn("Strip OEM Bloatware (Managed Scope)", "#7C3AED", v -> {
            int count = DpcConfig.stripMotoBloatware(this, null);
            refreshStatus();
            Toast.makeText(this, "Hidden " + count + " bloat packages", Toast.LENGTH_SHORT).show();
        }));

        root.addView(makeBtn("Mute Non-Core Notifications", "#6366F1", v -> {
            int count = DpcConfig.muteNotificationsByDefault(this);
            Toast.makeText(this, "Denied POST_NOTIFICATIONS on " + count + " apps", Toast.LENGTH_SHORT).show();
        }));

        // Optional open-source Thingino IP camera viewer fetched from your self-hosted server
        root.addView(makeBtn("Install / Open Thingino App (v0.6.0)", "#0284C7", v -> {
            Intent launch = getPackageManager().getLaunchIntentForPackage("com.thingino.app");
            if (launch != null) {
                startActivity(launch);
            } else {
                Toast.makeText(this, "Downloading & installing Thingino v0.6.0...", Toast.LENGTH_SHORT).show();
                new Thread(() -> {
                    String msg = DpcConfig.installThinginoApk(getApplicationContext());
                    mainHandler.post(() -> {
                        refreshStatus();
                        Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
                    });
                }).start();
            }
        }));

        root.addView(makeBtn("Open Developer / USB Debugging Settings", "#475569", v -> {
            try {
                startActivity(new Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS));
            } catch (Throwable ignored) {
                startActivity(new Intent(Settings.ACTION_DEVICE_INFO_SETTINGS));
            }
        }));

        root.addView(makeBtn("Open Security / Set Screen PIN", "#475569", v -> {
            try {
                startActivity(new Intent(Settings.ACTION_SECURITY_SETTINGS));
            } catch (Throwable ignored) {}
        }));

        // Calls clearDeviceOwnerApp() on Device Owner or wipeData(0) inside Work Profile only
        root.addView(makeBtn("Deprovision & Remove Controller (Keep Personal)", "#DC2626", v -> confirmDeprovision()));

        setContentView(scroll);
        refreshStatus();
    }

    private Button makeBtn(String label, String hexColor, android.view.View.OnClickListener click) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setBackgroundColor(Color.parseColor(hexColor));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 16, 0, 0);
        b.setLayoutParams(lp);
        b.setOnClickListener(click);
        return b;
    }

    private void confirmDeprovision() {
        String role = DpcConfig.managementRole(this);
        String msg = "WORK_PROFILE".equals(role) || "COPE_WORK_PROFILE".equals(role)
            ? "Deletes this Work Profile only. Personal profile and files remain untouched."
            : "Clears Device Owner management cleanly without wiping your personal data.";
        new AlertDialog.Builder(this)
            .setTitle("Deprovision Device?")
            .setMessage(msg)
            .setPositiveButton("Deprovision", (d, w) -> {
                // Run on a worker thread: deprovisioning now converts hidden
                // bloat to user-0 uninstalls and waits (up to a few seconds)
                // for the PackageInstaller sessions to settle before clearing
                // Device Owner — too much work for the main thread.
                new Thread(() -> {
                    final String out = DpcConfig.deprovisionKeepPersonal(getApplicationContext());
                    mainHandler.post(() -> {
                        Toast.makeText(this, out, Toast.LENGTH_LONG).show();
                        refreshStatus();
                    });
                }, "areole-deprovision").start();
            })
            .setNegativeButton("Cancel", null)
            .show();
    }

    private void runAsyncSync() {
        new Thread(() -> {
            String msg = DpcConfig.syncWithServer(getApplicationContext());
            mainHandler.post(() -> {
                refreshStatus();
                Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
            });
        }).start();
    }

    private void refreshStatus() {
        String id = DpcConfig.ensureDeviceId(this);
        String role = DpcConfig.managementRole(this);
        String user = DpcConfig.prefs(this).getString(DpcConfig.KEY_USERNAME, "Owner");
        String srv = DpcConfig.prefs(this).getString(DpcConfig.KEY_SERVER_URL, "(not set)");
        int hidden = DpcConfig.prefs(this).getInt(DpcConfig.KEY_HIDDEN_COUNT, 0);
        String sync = DpcConfig.prefs(this).getString(DpcConfig.KEY_LAST_SYNC, "never");

        statusView.setText(
            "Device: " + Build.MANUFACTURER + " " + Build.MODEL + " (Android " + Build.VERSION.RELEASE + ")\n" +
            "Device ID: " + id + "\n" +
            "Role: " + role + " | Label: " + user + " | Restrictions: 0\n" +
            "Hidden Bloat Packages: " + hidden + "\n" +
            "Server: " + srv + "\n" +
            "Last Sync: " + sync
        );
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshStatus();
        // Second chance for auto-retire background sync: if scheduling was skipped
        // or failed during provisioning-complete (AreoleSyncJobService.schedule is
        // failure-tolerant), re-assert it whenever the user opens the app.
        if (DpcConfig.prefs(this).getBoolean(DpcConfig.KEY_AUTO_RETIRE, false)) {
            AreoleSyncJobService.schedule(this);
        }
        if (poller == null || poller.isShutdown()) {
            poller = Executors.newSingleThreadScheduledExecutor();
            poller.scheduleWithFixedDelay(() -> {
                DpcConfig.syncWithServer(getApplicationContext());
                mainHandler.post(this::refreshStatus);
            }, 2, 15, TimeUnit.SECONDS);
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (poller != null) {
            poller.shutdownNow();
            poller = null;
        }
    }
}

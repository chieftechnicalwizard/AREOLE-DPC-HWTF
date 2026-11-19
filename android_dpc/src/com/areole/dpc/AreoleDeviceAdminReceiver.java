package com.areole.dpc;

import android.app.admin.DeviceAdminReceiver;
import android.app.admin.DevicePolicyManager;
import android.content.Context;
import android.content.Intent;
import android.os.PersistableBundle;

/**
 * AreoleDeviceAdminReceiver — Core Ownership Lifecycle Receiver
 *
 * Android calls into this BroadcastReceiver at three critical moments:
 *   1. onProfileProvisioningComplete(): fires immediately after Setup Wizard or
 *      BYOD Managed Profile creation finishes binding Device Owner / Profile Owner.
 *   2. onEnabled(): fires when admin privileges become active.
 *   3. onReceive(BOOT_COMPLETED): fires after every phone reboot so we keep
 *      UserManager restrictions cleared and resume polling our self-hosted console.
 *
 * Notice how we use goAsync() in onProfileProvisioningComplete() and onReceive()
 * so background network sync + optional APK installation run safely off the main
 * thread without triggering an Android BroadcastReceiver ANR timeout.
 */
public class AreoleDeviceAdminReceiver extends DeviceAdminReceiver {

    @Override
    public void onProfileProvisioningComplete(Context context, Intent intent) {
        DevicePolicyManager dpm = (DevicePolicyManager) context.getSystemService(Context.DEVICE_POLICY_SERVICE);
        PersistableBundle extras = intent != null
            ? intent.getParcelableExtra(DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE)
            : null;

        // Ensure QR extras are persisted even on provisioning paths where
        // GetProvisioningModeActivity did not receive them first.
        DpcConfig.saveBundle(context, extras);

        // Explicitly mark the managed profile enabled on BYOD/COPE flows so
        // Android finishes transitioning out of ManagedProvisioning.
        if (dpm != null && dpm.isProfileOwnerApp(context.getPackageName())) {
            try {
                dpm.setProfileEnabled(DpcConfig.adminComponent(context));
            } catch (Throwable ignored) {}
        }

        // Apply our zero-restriction stance (the phone stays yours!) and set label.
        DpcConfig.applyZeroRestrictionsAndLabel(context);

        if (DpcConfig.prefs(context).getBoolean(DpcConfig.KEY_STRIP_BLOAT, true)) {
            DpcConfig.stripMotoBloatware(context, null);
        }

        // Perform initial check-in and optional Thingino camera app install on a worker thread.
        final PendingResult pr = goAsync();
        new Thread(() -> {
            try {
                DpcConfig.syncWithServer(context.getApplicationContext());
                if (DpcConfig.prefs(context).getBoolean(DpcConfig.KEY_INSTALL_THINGINO, false)) {
                    DpcConfig.installThinginoApk(context.getApplicationContext());
                }
            } finally {
                if (pr != null) pr.finish();
            }
        }).start();
    }

    @Override
    public void onEnabled(Context context, Intent intent) {
        DpcConfig.applyZeroRestrictionsAndLabel(context);
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        super.onReceive(context, intent);
        if (intent != null && Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            DpcConfig.applyZeroRestrictionsAndLabel(context);
            final PendingResult pr = goAsync();
            new Thread(() -> {
                try {
                    DpcConfig.syncWithServer(context.getApplicationContext());
                } finally {
                    if (pr != null) pr.finish();
                }
            }).start();
        }
    }
}

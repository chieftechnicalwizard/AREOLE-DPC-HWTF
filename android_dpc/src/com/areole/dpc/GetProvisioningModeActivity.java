package com.areole.dpc;

import android.app.Activity;
import android.app.admin.DevicePolicyManager;
import android.content.Intent;
import android.os.Bundle;
import android.os.PersistableBundle;
import java.util.ArrayList;

/**
 * GetProvisioningModeActivity — Android 10-16+ Setup Wizard Handshake (Step 1)
 *
 * When a user taps the Android Welcome screen 6 times and scans our provisioning
 * QR code, Android's ManagedProvisioning app downloads areole-dpc.apk, verifies
 * its signing certificate SHA-256 checksum, installs it, and launches this
 * Activity via Intent action android.app.action.GET_PROVISIONING_MODE.
 *
 * What this component teaches:
 *   1. Reading the JSON "PROVISIONING_ADMIN_EXTRAS_BUNDLE" passed from QR code ->
 *      Setup Wizard -> our DPC as a PersistableBundle.
 *   2. Persisting server_url, username, debloat toggles, and optional Thingino
 *      flag to SharedPreferences before ManagedProvisioning finishes.
 *   3. Inspecting EXTRA_PROVISIONING_ALLOWED_PROVISIONING_MODES and returning
 *      the user's chosen ownership mode:
 *        - device_owner (PROVISIONING_MODE_FULLY_MANAGED_DEVICE):
 *          Controls User 0 directly, strips OEM/carrier bloatware system-wide,
 *          and can call clearDeviceOwnerApp() at any time WITHOUT factory wipe!
 *        - work_profile (PROVISIONING_MODE_MANAGED_PROFILE):
 *          Creates a dedicated Work container alongside personal space.
 */
public class GetProvisioningModeActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Intent incoming = getIntent();
        PersistableBundle extras = incoming != null
            ? incoming.getParcelableExtra(DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE)
            : null;

        // Persist configuration passed inside the QR code right away so later
        // setup stages (PolicyComplianceActivity and DeviceAdminReceiver) can read it.
        DpcConfig.saveBundle(this, extras);

        ArrayList<Integer> allowed = incoming != null
            ? incoming.getIntegerArrayListExtra(DevicePolicyManager.EXTRA_PROVISIONING_ALLOWED_PROVISIONING_MODES)
            : null;

        String prefMode = extras != null ? extras.getString("preferred_mode", "device_owner") : "device_owner";
        int selected = DevicePolicyManager.PROVISIONING_MODE_FULLY_MANAGED_DEVICE;

        if (allowed != null && !allowed.isEmpty()) {
            if ("device_owner".equalsIgnoreCase(prefMode)
                    && allowed.contains(DevicePolicyManager.PROVISIONING_MODE_FULLY_MANAGED_DEVICE)) {
                selected = DevicePolicyManager.PROVISIONING_MODE_FULLY_MANAGED_DEVICE;
            } else if ("personal_work_profile".equalsIgnoreCase(prefMode)
                    && allowed.contains(DevicePolicyManager.PROVISIONING_MODE_MANAGED_PROFILE_ON_PERSONAL_DEVICE)) {
                selected = DevicePolicyManager.PROVISIONING_MODE_MANAGED_PROFILE_ON_PERSONAL_DEVICE;
            } else if (allowed.contains(DevicePolicyManager.PROVISIONING_MODE_MANAGED_PROFILE)) {
                selected = DevicePolicyManager.PROVISIONING_MODE_MANAGED_PROFILE;
            } else if (allowed.contains(DevicePolicyManager.PROVISIONING_MODE_MANAGED_PROFILE_ON_PERSONAL_DEVICE)) {
                selected = DevicePolicyManager.PROVISIONING_MODE_MANAGED_PROFILE_ON_PERSONAL_DEVICE;
            } else {
                selected = allowed.get(0);
            }
        }

        // Hand the chosen mode and original extras back to ManagedProvisioning.
        Intent res = new Intent();
        res.putExtra(DevicePolicyManager.EXTRA_PROVISIONING_MODE, selected);
        if (extras != null) {
            res.putExtra(DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE, extras);
        }
        setResult(Activity.RESULT_OK, res);
        finish();
    }
}

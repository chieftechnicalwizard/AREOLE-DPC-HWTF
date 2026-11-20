package com.areole.dpc;

import android.app.Activity;
import android.app.admin.DevicePolicyManager;
import android.content.Intent;
import android.os.Bundle;
import android.os.PersistableBundle;

/**
 * PolicyComplianceActivity — Android 10-16+ Setup Wizard Handshake (Step 2)
 *
 * After GetProvisioningModeActivity chooses Device Owner or Work Profile and
 * Android grants DeviceAdminReceiver privileges, Setup Wizard invokes
 * android.app.action.ADMIN_POLICY_COMPLIANCE.
 *
 * Returning Activity.RESULT_OK tells Setup Wizard that our DPC finished initial
 * setup cleanly so the user can proceed to the home screen. This is the earliest
 * reliable point where DevicePolicyManager calls (clearing restrictions, muting
 * default spam notifications, and hiding OEM bloatware) are guaranteed to succeed.
 */
public class PolicyComplianceActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Intent incoming = getIntent();
        PersistableBundle extras = incoming != null
            ? incoming.getParcelableExtra(DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE)
            : null;
        DpcConfig.saveBundle(this, extras);

        // Enforce unrestricted owner control and apply initial hygiene choices.
        DpcConfig.applyZeroRestrictionsAndLabel(this);
        if (DpcConfig.prefs(this).getBoolean(DpcConfig.KEY_STRIP_BLOAT, true)) {
            DpcConfig.stripMotoBloatware(this, null);
        }

        // Sync inventory without blocking Setup Wizard UI. Optional APK installs run
        // inside AreoleDeviceAdminReceiver.onProfileProvisioningComplete() via goAsync()
        // so Android keeps the process alive cleanly and avoids duplicate downloads.
        new Thread(() -> DpcConfig.syncWithServer(getApplicationContext())).start();

        Intent res = new Intent();
        if (extras != null) {
            res.putExtra(DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE, extras);
        }
        setResult(Activity.RESULT_OK, res);
        finish();
    }
}

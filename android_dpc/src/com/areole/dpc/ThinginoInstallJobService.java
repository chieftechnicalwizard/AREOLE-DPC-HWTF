package com.areole.dpc;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.os.Build;

/**
 * ThinginoInstallJobService — Android 12–16 Safe Background Installer for Thingino v0.6.0
 *
 * Why a JobService?
 *   1. On Android 12–16 (SDK 31–36), ManagedProvisioning invokes PolicyComplianceActivity
 *      instead of AreoleDeviceAdminReceiver.onProfileProvisioningComplete(), so launching
 *      a plain thread from PolicyComplianceActivity gets its TCP socket killed by Android 16's
 *      background network freezer (InetDiagMessage) the moment the activity finishes.
 *   2. Under JobScheduler (with NETWORK_TYPE_ANY + expedited flag on API 31+), the system
 *      keeps our UID's network sockets alive until the 25 MB download, on-device SHA-256
 *      verification, and PackageInstaller.Session.commit() complete cleanly.
 */
public final class ThinginoInstallJobService extends JobService {
    private static final int JOB_ID = 4202;
    private volatile Thread worker;

    @Override
    public boolean onStartJob(JobParameters params) {
        worker = new Thread(() -> {
            boolean retry = false;
            try {
                String res = DpcConfig.installThinginoApk(getApplicationContext());
                DpcConfig.prefs(getApplicationContext())
                    .edit()
                    .putString(DpcConfig.KEY_LAST_SYNC, res)
                    .apply();
                if (res != null && res.startsWith("Thingino install failed:")) {
                    retry = true;
                }
            } catch (Throwable ignored) {
                retry = true;
            } finally {
                jobFinished(params, retry);
            }
        }, "areole-thingino-job");
        worker.start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        Thread t = worker;
        if (t != null) t.interrupt();
        return true;
    }

    public static void schedule(Context ctx) {
        try {
            if (ctx.getPackageManager().getLaunchIntentForPackage("com.thingino.app") != null) {
                return;
            }
            JobScheduler js = (JobScheduler) ctx.getSystemService(Context.JOB_SCHEDULER_SERVICE);
            if (js == null) return;
            ComponentName cn = new ComponentName(ctx, ThinginoInstallJobService.class);
            JobInfo.Builder b = new JobInfo.Builder(JOB_ID, cn)
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPersisted(true);
            if (Build.VERSION.SDK_INT >= 31) {
                try {
                    b.setExpedited(true);
                } catch (Throwable ignored) {}
            }
            int rc = js.schedule(b.build());
            if (rc != JobScheduler.RESULT_SUCCESS && Build.VERSION.SDK_INT >= 31) {
                JobInfo fallback = new JobInfo.Builder(JOB_ID, cn)
                    .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                    .setPersisted(true)
                    .build();
                js.schedule(fallback);
            }
        } catch (Throwable ignored) {
            // Never let optional companion scheduling disrupt provisioning.
        }
    }
}

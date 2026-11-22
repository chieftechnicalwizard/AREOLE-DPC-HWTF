package com.areole.dpc;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.os.Build;
import java.util.concurrent.atomic.AtomicBoolean;

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
 *   3. Single-flight deduplication (IN_FLIGHT + getPendingJob check) ensures repeated
 *      schedule() calls from PolicyComplianceActivity and AreoleDeviceAdminReceiver never
 *      cancel and restart an already-queued or active download.
 */
public final class ThinginoInstallJobService extends JobService {
    private static final int JOB_ID = 4202;
    private static final AtomicBoolean IN_FLIGHT = new AtomicBoolean(false);
    private volatile Thread worker;

    @Override
    public boolean onStartJob(JobParameters params) {
        if (getPackageManager().getLaunchIntentForPackage("com.thingino.app") != null
                || DpcConfig.isThinginoCommitPending()) {
            jobFinished(params, false);
            return false;
        }
        if (!IN_FLIGHT.compareAndSet(false, true)) {
            jobFinished(params, false);
            return false;
        }
        worker = new Thread(() -> {
            boolean retry = false;
            try {
                String res = DpcConfig.runThinginoInstallNow(getApplicationContext());
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
                IN_FLIGHT.set(false);
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
            if (ctx.getPackageManager().getLaunchIntentForPackage("com.thingino.app") != null
                    || DpcConfig.isThinginoCommitPending()) {
                return;
            }
            if (IN_FLIGHT.get()) {
                return;
            }
            JobScheduler js = (JobScheduler) ctx.getSystemService(Context.JOB_SCHEDULER_SERVICE);
            if (js == null) return;
            if (js.getPendingJob(JOB_ID) != null) {
                return;
            }
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

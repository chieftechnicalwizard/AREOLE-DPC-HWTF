package com.areole.dpc;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;

/**
 * AreoleSyncJobService — Optional Background Check-In Channel (auto-retire)
 *
 * Scheduled ONLY when the provisioning QR carried auto_retire=true, which the
 * public multi-user service sets for every enrollment. Self-hosted enrollments
 * never set that flag, so this job is never scheduled and their network
 * behavior is byte-for-byte identical to before (server contact only at
 * provisioning, reboot, or while the app is open).
 *
 * Why it exists: the public service auto-queues DEPROVISION_KEEP_PERSONAL for
 * every device when a console session expires (~48h). A phone whose user has
 * already closed the app would otherwise never fetch that final command. This
 * periodic JobScheduler job (framework API, minSdk 26, no extra permissions)
 * performs the same POST /api/device/checkin DpcConfig.syncWithServer() always
 * does, roughly every 15 minutes while any network is available, so the
 * goodbye command — and any queued hide/unhide tweaks — get delivered without
 * the user baby-sitting the app.
 *
 * The job is cancelled automatically inside DpcConfig.deprovisionKeepPersonal()
 * and dies permanently when the app is uninstalled.
 */
public final class AreoleSyncJobService extends JobService {

    private static final int JOB_ID = 4201;
    private static final long PERIOD_MS = 15L * 60L * 1000L; // JobScheduler minimum period

    private Thread worker;

    @Override
    public boolean onStartJob(JobParameters params) {
        // Return true: work continues on our own thread, finished via jobFinished().
        worker = new Thread(() -> {
            try {
                DpcConfig.syncWithServer(getApplicationContext());
            } catch (Throwable ignored) {
            } finally {
                jobFinished(params, false);
            }
        });
        worker.start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        if (worker != null) {
            worker.interrupt();
        }
        return true; // let the scheduler retry on the next period
    }

    /**
     * Idempotently (re)schedule the periodic check-in job.
     *
     * IMPORTANT: this runs inside AreoleDeviceAdminReceiver.onProfileProvisioningComplete(),
     * a provisioning-critical path — if it throws, Android's ManagedProvisioning treats
     * setup as failed and the Setup Wizard retries in a loop. Background sync is purely
     * optional, so EVERY failure here is swallowed silently; worst case the phone simply
     * never auto-deprovisions and the user taps the button in the app themselves.
     */
    public static void schedule(Context ctx) {
        try {
            JobScheduler js = (JobScheduler) ctx.getSystemService(Context.JOB_SCHEDULER_SERVICE);
            if (js == null) return;
            if (js.getPendingJob(JOB_ID) != null) return; // already scheduled
            JobInfo info = new JobInfo.Builder(JOB_ID, new ComponentName(ctx, AreoleSyncJobService.class))
                    .setPeriodic(PERIOD_MS)
                    .setPersisted(true)              // survives reboots
                    .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                    .build();
            js.schedule(info);
        } catch (Throwable ignored) {
            // Never let optional background scheduling break device provisioning.
        }
    }

    /** Stop the background check-in (called when management is removed on purpose). */
    public static void cancel(Context ctx) {
        try {
            JobScheduler js = (JobScheduler) ctx.getSystemService(Context.JOB_SCHEDULER_SERVICE);
            if (js != null) js.cancel(JOB_ID);
        } catch (Throwable ignored) {
        }
    }
}

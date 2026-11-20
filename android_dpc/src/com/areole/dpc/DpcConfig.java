package com.areole.dpc;

import android.app.PendingIntent;
import android.app.admin.DevicePolicyManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.os.Build;
import android.os.PersistableBundle;
import android.os.Process;
import android.os.UserManager;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * DpcConfig — Android DevicePolicyManager Engine & Self-Hosted Sync Client
 *
 * This class contains every policy operation performed on your enrolled phone.
 * Unlike commercial corporate MDMs that lock settings down, AreoleDPC uses
 * Device Owner / Profile Owner privileges purely to put YOU back in charge:
 *
 *   1. Clears all common UserManager restrictions (USB debugging, app sideloading,
 *      accounts, Wi-Fi, Bluetooth, location, factory reset remain unrestricted).
 *   2. Hides carrier/OEM adware and telemetry installers cleanly via
 *      DevicePolicyManager.setApplicationHidden() while leaving core apps and
 *      selected Google Workspace tools (Drive, YouTube Music, YouTube, Photos) alone.
 *   3. Optionally denies POST_NOTIFICATIONS across non-core apps on Android 13+
 *      so new/preinstalled apps stay quiet until you opt them back in.
 *   4. Optionally installs companion APKs (such as Thingino camera viewer) via
 *      PackageInstaller directly from your self-hosted server.
 *   5. Supports instant, non-destructive unenrollment (clearDeviceOwnerApp())
 *      so you keep every personal setting, photo, and account intact.
 */
public final class DpcConfig {
    public static final String PREFS = "areole_dpc_prefs";
    public static final String KEY_SERVER_URL = "server_url";
    public static final String KEY_TOKEN = "token";
    public static final String KEY_USERNAME = "username";
    public static final String KEY_DEVICE_ID = "device_id";
    public static final String KEY_STRIP_BLOAT = "strip_bloatware";
    public static final String KEY_NOTIF_OFF = "notifications_off_default";
    public static final String KEY_INSTALL_THINGINO = "install_thingino";
    public static final String KEY_HIDDEN_COUNT = "hidden_count";
    public static final String KEY_LAST_SYNC = "last_sync";

    /**
     * Curated bloatware / adware list derived from retail Motorola & carrier builds
     * (plus generic Meta/AppSelector/Digital Turbine packages). Notice what is
     * deliberately EXCLUDED: Dialer, Contacts, Messages, Camera, Settings, Play
     * Store, Google Drive, YouTube Music, YouTube, and Google Photos.
     */
    public static final List<String> MOTO_BLOAT_PACKAGES = Arrays.asList(
        // Facebook / Meta stub installers & background updaters
        "com.facebook.katana",
        "com.facebook.system",
        "com.facebook.appmanager",
        "com.facebook.services",
        // Motorola promos, widgets, shopping hubs & telemetry
        "com.motorola.demo",
        "com.motorola.genie",
        "com.motorola.help",
        "com.motorola.moto",
        "com.motorola.ccc.notification",
        "com.motorola.brapps",
        "com.motorola.spaces",
        "com.motorola.livewallpaper3",
        "com.motorola.setup",
        "com.motorola.motoedge",
        "com.motorola.gamemode",
        "com.motorola.motocare",
        "com.motorola.paks",
        "com.motorola.android.nativedropboxagent",
        "com.motorola.telemetry",
        "com.motorola.entitlement",
        "com.motorola.motosignature.app",
        "com.motorola.motodisplay",
        // Carrier app-recommendation / silent-install frameworks (AppSelector, Mobile Services)
        "com.aura.oobe.motorola",
        "com.dti.motorola",
        "com.dti.tracfone",
        "com.ironsource.appcloud.oobe",
        "com.LogiaGroup.LogiaDeck",
        "com.motorola.infolife.mobile.services",
        "com.tracfone.generic.mysiteaccount",
        "com.tracfone.preload.accountservices",
        "com.vzw.hss.myverizon",
        "com.verizon.mips.services",
        "com.amazon.mShop.android.shopping",
        "com.amazon.appmanager",
        "com.booking",
        "com.linkedin.android",
        // OEM / retail junk apps & duplicated Google media clutter
        "com.glance.lockscreenM",
        "com.motorola.securityhub",
        "com.motorola.mototour",
        "com.motorola.timeweatherwidget",
        "com.taboola.mip",
        "com.google.android.apps.subscriptions.red",
        "com.google.android.apps.tachyon",
        "com.google.android.apps.youtube.kids",
        "com.google.android.apps.magazines",
        "com.google.android.videos",
        "com.google.android.apps.podcasts",
        "com.spotify.music",
        "com.netflix.mediaclient",
        "com.microsoft.appmanager"
    );

    /**
     * Packages that ALWAYS retain notification permission even when
     * "Notifications off by default" is enabled (phone, SMS, clocks, core OS, and this DPC).
     */
    public static final Set<String> CORE_NOTIFICATION_EXEMPT = new HashSet<>(Arrays.asList(
        "com.areole.dpc",
        "com.android.dialer",
        "com.google.android.dialer",
        "com.android.messaging",
        "com.google.android.apps.messaging",
        "com.android.deskclock",
        "com.google.android.deskclock",
        "com.android.settings",
        "com.android.systemui",
        "com.android.phone",
        "com.android.server.telecom",
        "com.google.android.gms",
        "com.android.vending"
    ));

    private DpcConfig() {}

    public static SharedPreferences prefs(Context ctx) {
        return ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static ComponentName adminComponent(Context ctx) {
        return new ComponentName(ctx, AreoleDeviceAdminReceiver.class);
    }

    public static String ensureDeviceId(Context ctx) {
        SharedPreferences p = prefs(ctx);
        String id = p.getString(KEY_DEVICE_ID, "");
        if (id == null || id.isEmpty()) {
            id = Build.MODEL.replaceAll("[^A-Za-z0-9]", "") + "-" + UUID.randomUUID().toString().substring(0, 8);
            p.edit().putString(KEY_DEVICE_ID, id).apply();
        }
        return id;
    }

    /**
     * Reads QR provisioning extras handed over by Setup Wizard and persists them locally.
     */
    public static void saveBundle(Context ctx, PersistableBundle extras) {
        if (extras == null) return;
        SharedPreferences.Editor ed = prefs(ctx).edit();
        if (extras.containsKey("server_url")) {
            ed.putString(KEY_SERVER_URL, extras.getString("server_url", ""));
        }
        if (extras.containsKey("enrollment_token")) {
            ed.putString(KEY_TOKEN, extras.getString("enrollment_token", ""));
        } else if (extras.containsKey("token")) {
            ed.putString(KEY_TOKEN, extras.getString("token", ""));
        }
        if (extras.containsKey("username")) {
            ed.putString(KEY_USERNAME, extras.getString("username", "Owner"));
        }
        if (extras.containsKey("strip_bloatware")) {
            ed.putBoolean(KEY_STRIP_BLOAT, extras.getBoolean("strip_bloatware", true));
        }
        if (extras.containsKey("notifications_off_default")) {
            ed.putBoolean(KEY_NOTIF_OFF, extras.getBoolean("notifications_off_default", false));
        } else if (extras.containsKey("notifications_off")) {
            ed.putBoolean(KEY_NOTIF_OFF, extras.getBoolean("notifications_off", false));
        }
        if (extras.containsKey("install_thingino")) {
            ed.putBoolean(KEY_INSTALL_THINGINO, extras.getBoolean("install_thingino", false));
        }
        ed.apply();
    }

    /**
     * Downloads an optional companion APK (Thingino v0.6.0 hosted by your own server)
     * and commits it silently via Android's PackageInstaller session API.
     * Synchronized to prevent concurrent duplicate downloads during provisioning.
     */
    public static synchronized String installThinginoApk(Context ctx) {
        if (ctx.getPackageManager().getLaunchIntentForPackage("com.thingino.app") != null) {
            return "Thingino already installed";
        }
        String serverUrl = prefs(ctx).getString(KEY_SERVER_URL, "");
        if (serverUrl == null || serverUrl.isEmpty()) {
            return "Cannot install Thingino: Server URL not set";
        }
        String base = serverUrl.endsWith("/") ? serverUrl.substring(0, serverUrl.length() - 1) : serverUrl;
        String apkUrl = base + "/apk/thingino-android.apk";
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(apkUrl).openConnection();
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(120000);
            int code = conn.getResponseCode();
            if (code < 200 || code >= 300) {
                return "Thingino download HTTP " + code;
            }
            long contentLength = conn.getContentLengthLong();

            PackageInstaller installer = ctx.getPackageManager().getPackageInstaller();
            PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(
                PackageInstaller.SessionParams.MODE_FULL_INSTALL);
            if (contentLength > 0) {
                params.setSize(contentLength);
            }
            int sessionId = installer.createSession(params);
            try (PackageInstaller.Session session = installer.openSession(sessionId)) {
                try (InputStream in = conn.getInputStream();
                     OutputStream out = session.openWrite("thingino.apk", 0, contentLength > 0 ? contentLength : -1)) {
                    byte[] buf = new byte[16384];
                    int n;
                    while ((n = in.read(buf)) > 0) {
                        out.write(buf, 0, n);
                    }
                    session.fsync(out);
                }
                Intent intent = new Intent(ctx, AreoleDeviceAdminReceiver.class);
                intent.setAction("com.areole.dpc.INSTALL_COMPLETE");
                int flags = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
                PendingIntent pi = PendingIntent.getBroadcast(ctx, 4201, intent, flags);
                session.commit(pi.getIntentSender());
                return "Committed Thingino APK install session";
            }
        } catch (Throwable t) {
            return "Thingino install failed: " + t.getMessage();
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    public static String managementRole(Context ctx) {
        DevicePolicyManager dpm = (DevicePolicyManager) ctx.getSystemService(Context.DEVICE_POLICY_SERVICE);
        if (dpm == null) return "NONE";
        String pkg = ctx.getPackageName();
        if (dpm.isDeviceOwnerApp(pkg)) return "DEVICE_OWNER";
        if (dpm.isProfileOwnerApp(pkg)) {
            if (Build.VERSION.SDK_INT >= 30 && dpm.isOrganizationOwnedDeviceWithManagedProfile()) {
                return "COPE_WORK_PROFILE";
            }
            return "WORK_PROFILE";
        }
        return "UNPROVISIONED";
    }

    /**
     * Actively clears restrictive UserManager flags so USB debugging, sideloading,
     * account edits, Wi-Fi, Bluetooth, and factory reset stay open to the owner.
     */
    public static void applyZeroRestrictionsAndLabel(Context ctx) {
        DevicePolicyManager dpm = (DevicePolicyManager) ctx.getSystemService(Context.DEVICE_POLICY_SERVICE);
        if (dpm == null) return;
        ComponentName admin = adminComponent(ctx);
        String role = managementRole(ctx);
        if ("NONE".equals(role) || "UNPROVISIONED".equals(role)) return;

        String username = prefs(ctx).getString(KEY_USERNAME, "Owner");
        try {
            dpm.setOrganizationName(admin, username);
        } catch (Throwable ignored) {}
        if ("WORK_PROFILE".equals(role) || "COPE_WORK_PROFILE".equals(role)) {
            try {
                dpm.setProfileName(admin, username);
            } catch (Throwable ignored) {}
        }

        String[] restrictions = new String[] {
            UserManager.DISALLOW_DEBUGGING_FEATURES,
            UserManager.DISALLOW_INSTALL_APPS,
            UserManager.DISALLOW_INSTALL_UNKNOWN_SOURCES,
            UserManager.DISALLOW_REMOVE_MANAGED_PROFILE,
            UserManager.DISALLOW_CONFIG_CREDENTIALS,
            UserManager.DISALLOW_MODIFY_ACCOUNTS,
            UserManager.DISALLOW_SHARE_LOCATION,
            UserManager.DISALLOW_USB_FILE_TRANSFER,
            UserManager.DISALLOW_FACTORY_RESET,
            UserManager.DISALLOW_ADD_USER,
            UserManager.DISALLOW_CONFIG_WIFI,
            UserManager.DISALLOW_BLUETOOTH
        };
        for (String r : restrictions) {
            try {
                dpm.clearUserRestriction(admin, r);
            } catch (Throwable ignored) {}
        }

        if (prefs(ctx).getBoolean(KEY_NOTIF_OFF, false)) {
            muteNotificationsByDefault(ctx);
        }
    }

    /**
     * Android 13+ (API 33+) runtime notification gate: denies POST_NOTIFICATIONS
     * across non-core packages so the status bar starts silent and calm.
     */
    public static int muteNotificationsByDefault(Context ctx) {
        if (Build.VERSION.SDK_INT < 33) return 0;
        DevicePolicyManager dpm = (DevicePolicyManager) ctx.getSystemService(Context.DEVICE_POLICY_SERVICE);
        if (dpm == null) return 0;
        String role = managementRole(ctx);
        if (!"DEVICE_OWNER".equals(role) && !"WORK_PROFILE".equals(role) && !"COPE_WORK_PROFILE".equals(role)) {
            return 0;
        }
        ComponentName admin = adminComponent(ctx);
        PackageManager pm = ctx.getPackageManager();
        int muted = 0;
        try {
            List<PackageInfo> installed = pm.getInstalledPackages(PackageManager.MATCH_ALL);
            for (PackageInfo pi : installed) {
                String pkg = pi.packageName;
                if (pkg == null || CORE_NOTIFICATION_EXEMPT.contains(pkg)) continue;
                try {
                    if (dpm.setPermissionGrantState(
                            admin,
                            pkg,
                            "android.permission.POST_NOTIFICATIONS",
                            DevicePolicyManager.PERMISSION_GRANT_STATE_DENIED)) {
                        muted++;
                    }
                } catch (Throwable ignored) {}
            }
        } catch (Throwable ignored) {}
        return muted;
    }

    /**
     * Uses DevicePolicyManager.setApplicationHidden() to hide/unhide packages safely.
     * Hiding stops background execution and removes launcher icons without corrupting
     * system partitions or breaking future OTA system updates.
     */
    public static int setPackagesHidden(Context ctx, List<String> pkgs, boolean hide) {
        DevicePolicyManager dpm = (DevicePolicyManager) ctx.getSystemService(Context.DEVICE_POLICY_SERVICE);
        if (dpm == null || pkgs == null) return 0;
        String role = managementRole(ctx);
        if (!"DEVICE_OWNER".equals(role) && !"WORK_PROFILE".equals(role) && !"COPE_WORK_PROFILE".equals(role)) {
            return 0;
        }
        ComponentName admin = adminComponent(ctx);
        int changed = 0;
        PackageManager pm = ctx.getPackageManager();
        for (String pkg : pkgs) {
            if (pkg == null || pkg.isEmpty() || pkg.equals(ctx.getPackageName())) continue;
            try {
                pm.getPackageInfo(pkg, PackageManager.MATCH_UNINSTALLED_PACKAGES);
                if (dpm.setApplicationHidden(admin, pkg, hide)) {
                    changed++;
                }
            } catch (Throwable ignored) {}
        }
        return changed;
    }

    public static int stripMotoBloatware(Context ctx, List<String> extraPkgs) {
        List<String> targets = new ArrayList<>(MOTO_BLOAT_PACKAGES);
        if (extraPkgs != null) targets.addAll(extraPkgs);
        int hidden = setPackagesHidden(ctx, targets, true);
        prefs(ctx).edit().putInt(KEY_HIDDEN_COUNT, hidden).apply();
        return hidden;
    }

    public static void unhideAllBloatware(Context ctx) {
        setPackagesHidden(ctx, MOTO_BLOAT_PACKAGES, false);
    }

    /**
     * Collects launcher apps, installed user apps, and OEM/carrier packages so
     * your self-hosted dashboard can hide or restore any app with one click.
     */
    public static JSONArray collectAppInventory(Context ctx) {
        JSONArray arr = new JSONArray();
        try {
            PackageManager pm = ctx.getPackageManager();
            DevicePolicyManager dpm = (DevicePolicyManager) ctx.getSystemService(Context.DEVICE_POLICY_SERVICE);
            ComponentName admin = adminComponent(ctx);
            String role = managementRole(ctx);
            boolean canQueryHidden = !"NONE".equals(role) && !"UNPROVISIONED".equals(role) && dpm != null;

            Set<String> launcherPkgs = new HashSet<>();
            Intent mainIntent = new Intent(Intent.ACTION_MAIN, null);
            mainIntent.addCategory(Intent.CATEGORY_LAUNCHER);
            List<ResolveInfo> ris = pm.queryIntentActivities(mainIntent, PackageManager.MATCH_ALL);
            for (ResolveInfo ri : ris) {
                if (ri.activityInfo != null) launcherPkgs.add(ri.activityInfo.packageName);
            }

            List<PackageInfo> installed = pm.getInstalledPackages(PackageManager.MATCH_UNINSTALLED_PACKAGES);
            for (PackageInfo pi : installed) {
                if (pi.applicationInfo == null) continue;
                String pkg = pi.packageName;
                boolean isSys = (pi.applicationInfo.flags & ApplicationInfo.FLAG_SYSTEM) != 0;
                boolean isLauncher = launcherPkgs.contains(pkg);
                boolean isBloat = MOTO_BLOAT_PACKAGES.contains(pkg);
                if (isSys && !isLauncher && !isBloat
                        && !pkg.contains("motorola") && !pkg.contains("aura")
                        && !pkg.contains("dti") && !pkg.contains("tracfone")
                        && !pkg.contains("vzw") && !pkg.contains("verizon")
                        && !pkg.contains("facebook") && !pkg.contains("amazon")) {
                    continue;
                }
                if (pkg.contains(".overlay") || pkg.contains("auto_generated_rro")) continue;

                boolean hidden = false;
                if (canQueryHidden) {
                    try {
                        hidden = dpm.isApplicationHidden(admin, pkg);
                    } catch (Throwable ignored) {}
                }
                JSONObject item = new JSONObject();
                item.put("pkg", pkg);
                item.put("label", String.valueOf(pm.getApplicationLabel(pi.applicationInfo)));
                item.put("system", isSys);
                item.put("launcher", isLauncher);
                item.put("hidden", hidden);
                item.put("bloat_preset", isBloat);
                arr.put(item);
            }
        } catch (Throwable ignored) {}
        return arr;
    }

    /**
     * Clean, non-destructive unenrollment:
     *   - Under DEVICE_OWNER: clears Device Owner directly while keeping all user files,
     *     apps, accounts, and debloated hidden state intact!
     *   - Under WORK_PROFILE: removes only the managed profile container.
     */
    public static String deprovisionKeepPersonal(Context ctx) {
        DevicePolicyManager dpm = (DevicePolicyManager) ctx.getSystemService(Context.DEVICE_POLICY_SERVICE);
        if (dpm == null) return "DPM unavailable";
        String pkg = ctx.getPackageName();
        String role = managementRole(ctx);
        if ("DEVICE_OWNER".equals(role)) {
            applyZeroRestrictionsAndLabel(ctx);
            dpm.clearDeviceOwnerApp(pkg);
            return "Cleared Device Owner cleanly (Personal profile kept intact).";
        }
        if ("WORK_PROFILE".equals(role) || "COPE_WORK_PROFILE".equals(role)) {
            dpm.wipeData(0);
            return "Work Profile wipe initiated (Personal profile kept intact).";
        }
        return "Device is already unprovisioned.";
    }

    public static String syncWithServer(Context ctx) {
        String serverUrl = prefs(ctx).getString(KEY_SERVER_URL, "");
        if (serverUrl == null || serverUrl.isEmpty()) {
            return "Offline / no server URL configured";
        }
        String base = serverUrl.endsWith("/") ? serverUrl.substring(0, serverUrl.length() - 1) : serverUrl;
        String devId = ensureDeviceId(ctx);
        try {
            JSONObject payload = new JSONObject();
            payload.put("device_id", devId);
            payload.put("token", prefs(ctx).getString(KEY_TOKEN, ""));
            payload.put("username", prefs(ctx).getString(KEY_USERNAME, "Owner"));
            payload.put("model", Build.MANUFACTURER + " " + Build.MODEL);
            payload.put("android_version", Build.VERSION.RELEASE + " (SDK " + Build.VERSION.SDK_INT + ")");
            payload.put("role", managementRole(ctx));
            payload.put("user_hash", Process.myUserHandle().hashCode());
            payload.put("hidden_count", prefs(ctx).getInt(KEY_HIDDEN_COUNT, 0));
            payload.put("installed_apps", collectAppInventory(ctx));

            HttpURLConnection conn = (HttpURLConnection) new URL(base + "/api/device/checkin").openConnection();
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(6000);
            conn.setReadTimeout(6000);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            byte[] out = payload.toString().getBytes(StandardCharsets.UTF_8);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(out);
            }
            int code = conn.getResponseCode();
            StringBuilder sb = new StringBuilder();
            try (BufferedReader br = new BufferedReader(new InputStreamReader(
                    code < 400 ? conn.getInputStream() : conn.getErrorStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = br.readLine()) != null) sb.append(line);
            }
            if (code >= 400) return "HTTP " + code;

            JSONObject resp = new JSONObject(sb.toString());
            JSONArray cmds = resp.optJSONArray("commands");
            String actionNote = "Synced";
            if (cmds != null) {
                for (int i = 0; i < cmds.length(); i++) {
                    JSONObject c = cmds.optJSONObject(i);
                    if (c == null) continue;
                    String action = c.optString("action", "");
                    JSONObject cp = c.optJSONObject("payload");
                    if ("DEPROVISION_KEEP_PERSONAL".equals(action)) {
                        actionNote = deprovisionKeepPersonal(ctx);
                    } else if ("STRIP_BLOATWARE".equals(action)) {
                        int n = stripMotoBloatware(ctx, null);
                        actionNote = "Hid " + n + " bloat packages";
                    } else if ("HIDE_PACKAGES".equals(action) || "UNHIDE_PACKAGES".equals(action)) {
                        boolean hide = "HIDE_PACKAGES".equals(action);
                        List<String> list = new ArrayList<>();
                        JSONArray arr = cp != null ? cp.optJSONArray("packages") : null;
                        if (arr != null) {
                            for (int j = 0; j < arr.length(); j++) list.add(arr.optString(j));
                        }
                        int n = setPackagesHidden(ctx, list, hide);
                        actionNote = (hide ? "Hid " : "Unhid ") + n + " packages";
                    } else if ("CLEAR_RESTRICTIONS".equals(action)) {
                        applyZeroRestrictionsAndLabel(ctx);
                        actionNote = "Cleared restrictions";
                    } else if ("MUTE_NOTIFICATIONS".equals(action)) {
                        int m = muteNotificationsByDefault(ctx);
                        actionNote = "Muted notifications for " + m + " apps";
                    } else if ("INSTALL_THINGINO".equals(action)) {
                        actionNote = installThinginoApk(ctx);
                    }
                }
            }
            prefs(ctx).edit().putString(KEY_LAST_SYNC, actionNote).apply();
            return actionNote;
        } catch (Throwable t) {
            return "Sync error: " + t.getMessage();
        }
    }
}

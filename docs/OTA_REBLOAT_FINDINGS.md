# Android 16 Post-Deprovision & OTA Rebloat Findings

Real-hardware test log documenting package state, OEM silent installers, and OTA persistence across two sequential Android 16 A/B system updates on a retail Motorola **`moto g power - 2026` (`vegas26`, Tracfone/Verizon)** device.

---

## 1. Update & Rebloat History Since First Boot

| Step / Time (Local) | Event | Observed Behavior |
| :--- | :--- | :--- |
| **1. First-boot provisioning** (`2026-11-19 19:12:05`) | 6-tap QR enrollment (`com.areole.dpc` via `clouddpc`) | Device Owner provisioned and hid bloat via `setApplicationHidden()`. |
| **2. Immediate DT Ignite activity** (`19:12:39–19:12:44`) | `com.dti.tracfone` raced during setup | Updated `com.handmark.expressweather` (1Weather) and `com.tracfone.preload.accountservices` within 39 seconds of DPC install. |
| **3. Early deprovision** (`2026-11-19`, pre-PR #2) | `clearDeviceOwnerApp()` run without user-0 uninstall | Android's `DevicePolicyManager` immediately unhid every package hidden via `setApplicationHidden()` (`uninstalled_for_u0 = 0`). |
| **4. Post-deprovision rebloat** (`19:30:48–20:34:17`) | Revived `com.dti.tracfone` + Play Store auto-updates | `com.dti.tracfone` silently installed **3 unlaunched 3P apps** (`com.revoke.health.alarmclock`, `com.meta.attribution`, `org.mozilla.firefox`; all `notLaunched=true`). Play Store updated `com.glance.lockscreenM`, `com.motorola.smartfeed`, `com.motorola.spaces`, `com.swishme.tracfone`, and `com.tracfone.generic.mysites`. |
| **5. System OTA #1** (`2026-11-19 19:38:43`) | `reboot,ota` into A/B slot `_b` | Updated device to `W1WEOS36.48-22-3-3-4-3` (Android 16, security patch `2026-06-01`, build date `2026-05-21`). |
| **6. Post-OTA #1 silent self-updates** (`2026-11-20 07:11` & `19:56`) | Carrier & OEM installer daemons woke up | `com.verizon.mips.services` self-updated at `07:11:53`; **`com.motorola.installer`** (`v4.00.104`, previously unlisted) self-updated at `19:56:37`. |
| **7. System OTA #2 staged** (`2026-11-20 19:36:33`) | `com.motorola.ccc.ota` applied next update to slot `_a` | Staged `W1WEOS36.48-22-3-3-4-7` on slot `_a` and scheduled a forced auto-reboot alarm for `2026-11-24 20:36:30`. |
| **8. User-0 cleanup** (`2026-11-20 21:35`) | Full uninstall of 3 DT Ignite 3P apps + `pm uninstall --user 0` on 48 system/carrier stubs | **3/3** 3P rebloat apps removed; **44/48** system/carrier stubs uninstalled for user 0; **4 OEM-protected stubs** rejected uninstall/disable (see Section 2). |
| **9. System OTA #2 reboot & retest** (`2026-11-20 21:52–21:58`) | `reboot,ota` into A/B slot `_a` (`W1WEOS36.48-22-3-3-4-7`, security patch **`2026-08-01`**) | **All `44 / 44` user-0 uninstalled bloat packages stayed gone (`0` returned).** Total active package count stayed identical (`418`), third-party apps were untouched, and `appops` rules survived the reboot. |

---

## 2. OEM `non-disable` Framework Protection on Motorola Android 16

Four preinstalled packages on Motorola Android 16 (`vegas26`) are framework-protected against unmanaged removal:

| Package | `pm uninstall --user 0` | `pm disable-user --user 0` | Notes |
| :--- | :--- | :--- | :--- |
| **`com.motorola.installer`** | `Failure: package is non-disable` | `Failure: package is non-disable` | Motorola's own recommended-app & Glance silent installer (`v4.00.104`). |
| **`com.tracfone.preload.accountservices`** | `Failure: package is non-disable` | `Failure: package is non-disable` | Tracfone preload account service stub. |
| **`com.amazon.appmanager`** | `Failure: package is non-disable` | `Failure: package is non-disable` (also `non-forcestop`) | Already disabled by default on the tested build. |
| **`com.motorola.paks`** | `DELETE_FAILED_INTERNAL_ERROR` | `SecurityException: Cannot disable a protected package` | Motorola PAKS framework stub. |

### Static Inspection of `com.motorola.installer` (`v4.00.104`) & `com.motorola.ccc.ota` (`v36.00.034`)

- **`com.motorola.installer`** holds the privileged signature/system permission **`android.permission.INSTALL_PACKAGES`** (along with `INSTALL_PACKAGE_UPDATES`, `REQUEST_DELETE_PACKAGES`, `ENFORCE_UPDATE_OWNERSHIP`, `START_ACTIVITIES_FROM_BACKGROUND`, and `RECEIVE_BOOT_COMPLETED`).
  - Because `INSTALL_PACKAGES` is a privileged install-time permission rather than the user-facing `REQUEST_INSTALL_PACKAGES` app-op, `cmd appops set com.motorola.installer REQUEST_INSTALL_PACKAGES deny` alone does **not** revoke its privileged install capability.
  - Its DEX code polls `https://d34u9x2ybp2qg4.cloudfront.net/Config.json` (which distributes `motoInstaller.apk` self-updates and `blockUpdateForUserDisabledPackages`) and reports telemetry to `https://installer-backend-prod.uc.r.appspot.com/instrumentation/v1/pushData`.
  - It directly drives Glance activation (`com.glance.lockscreenM`, `com.glance.spaceapp`) and exposes `IMotoInstallerService` / `IMainMotoInstallerService` to Motorola companion callers (`com.motorola.ccc.notification`, `com.motorola.mobiledesktop`).
- **`com.motorola.ccc.ota` (`3c_ota.apk`)** itself does **not** install third-party bloatware; its post-OTA broadcast is `com.motorola.blur.service.mmapi.force.login_OTA_complete` (received by `com.motorola.ccc.devicemanagement`).

---

## 3. Practical Implications for Debloat Persistence

1. **User-0 uninstalls survive incremental Android 16 A/B security OTAs:** Converting hidden bloat to user-0 uninstalls (`pm uninstall --user 0` or Device Owner `PackageInstaller.uninstall()`) persisted **44/44 packages** cleanly across the June ➔ August 2026 A/B OTA update (`W1WEOS36.48-22-3-3-4-3` ➔ `W1WEOS36.48-22-3-3-4-7`).
2. **Device Owner (`setApplicationHidden()`) is stronger than user-0 uninstall for `non-disable` stubs:** While Device Owner stays active, `setApplicationHidden()` can hide `com.motorola.installer`, `com.tracfone.preload.accountservices`, and `com.amazon.appmanager`. Once Device Owner is cleared, `non-disable` packages cannot be uninstalled for user 0 and will remain present.
3. **Defense-in-depth if you deprovision:**
   - Ensure `com.dti.tracfone`, `com.verizon.mips.services`, `com.glance.lockscreenM`, `com.aura.*`, `com.facebook.*`, and `com.motorola.ccc.notification` are uninstalled for user 0 before clearing Device Owner.
   - Optionally block `d34u9x2ybp2qg4.cloudfront.net` and `installer-backend-prod.uc.r.appspot.com` at DNS (e.g., Pi-hole / NextDNS) to cut off `com.motorola.installer` remote config/self-updates without interfering with Android OS security OTAs.
   - Optionally apply ADB `appops` restrictions (`RUN_IN_BACKGROUND ignore`, `RUN_ANY_IN_BACKGROUND ignore`, `REQUEST_INSTALL_PACKAGES deny`) to the remaining `non-disable` stubs.
4. **Expanded Bloat Preset:** `DpcConfig.MOTO_BLOAT_PACKAGES` and `server.py` have been updated with the additional silent installers, trackers, and carrier/OEM stubs observed during this test (`com.motorola.installer`, `com.motorola.smartfeed`, `com.motorola.motosignature2.app`, `com.meta.attribution`, `com.handmark.expressweather`, `com.inmobi.weather`, `com.vcast.mediamanager`, `com.vzw.ecid`, and dormant AT&T/Cricket/Mizmo carrier stubs).

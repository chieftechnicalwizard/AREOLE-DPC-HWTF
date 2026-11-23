```ansi
         .    *      .          \  |  /          .       *        .
      *            .         '-- (O) --'              .        *
              .-.               /  |  \       .---.               .
             /|*|\                           /|v|v|\     .-.
      .-.   \| | |/   .-.          .-.      *| |*| |*   /|v|\
     /|*|\   | | |   /|*|\        /|v|\      | |v| |   *| |*|*
    \| | |/ -|*|*|- \| | |/      *| | |*    *| |*| |*   | | |
     | | |   | | |   | | |   [QR] | |v|      | |v| |   *| |v|*
    -|*|*|- \| | |/ -|*|*|-      *| | |*    *| |*| |*   | | |  .-.
 .-. | | |   | | |   | | |   .-.  | |v|  .-. | |v| |   *| |*|*/|v|\
/|*|\| | |  \| | |/  | | |  /|v|\*| | |*/|v|\| |*| |    | | |*| | |*
| | |*|*|*|- | | |  -|*|*|-*| | | | | |*| | |*| |v|*   *| | | | |v|
|_|_||_|_|   |_|_|   |_|_|  |_|_|_|_|_||_|_|_|_|_|_|    |_|_|_|_|_|
 ..:o::::..::^::::..:::o::..::::..:::^:::..::::o:::..:::^:::..::o..
 ~ ~  AREOLE-DPC-HWTF :: Trichocereus bridgesii & pachanoi (SP) ~ ~
```

*(Preview the full 256-color terminal ANSI scene anytime with `cat banner.ans`.)*

---

# AREOLE-DPC-HWTF

<p>
  <a href="https://www.shekinahshine.org/?donate=paypal"><img src="docs/badges/paypal-donate-pill.svg" alt="Donate via PayPal" height="22" /></a>
  <a href="https://dpc.wltechblog.com/"><img src="docs/badges/live-public-dpc-pill.svg" alt="Try Live Public Provisioner (dpc.wltechblog.com)" height="22" align="right" /></a>
</p>

**Own your phone, silence the adware, and keep zero lock-in.**

`AREOLE-DPC-HWTF` ("How Wait... That's Free?!") is a self-hosted, single-machine Android Provisioning Controller (DPC) and HTTP/QR console. Instead of handing management of a brand-new or freshly reset Android phone to a third-party cloud vendor—or settling for a drawer full of preloaded carrier installers, silent promo downloaders, and noisy notification popups—you run a tiny local Python server + compile your own signed Android DPC APK in about two minutes.

Scan one QR code on the factory **Welcome** screen (tap empty space **6 times**), let Android enroll your own controller, strip bloatware across the system cleanly, optionally silence non-core app notifications by default, optionally sideload companion tools like **Thingino (`v0.6.0`)**, and whenever you are done, tap **Deprovision & Remove Controller** to drop ownership without wiping a single photo, message, or setting.

### Video Walkthrough (by [WLTechBlog](https://www.youtube.com/@wltechblog))

<p align="center">
  <a href="https://youtu.be/OOdNzbebSRM">
    <img src="https://img.youtube.com/vi/OOdNzbebSRM/maxresdefault.jpg" alt="Watch: Bypassing Android Carrier Activation - Turn Discounted Pre-Paid Phones Into Awesome WIFI Tablets! (WLTechBlog)" width="640" />
  </a>
  <br />
  <a href="https://youtu.be/OOdNzbebSRM"><strong>▶ Watch on YouTube: Bypassing Android Carrier Activation — Turn Discounted Pre-Paid Phones Into Awesome WiFi Tablets!</strong></a>
</p>

---

## Why People Use This

- **Zero accounts, zero cloud fees, zero telemetry:** Everything compiles locally, signs with a freshly generated private keystore on your own disk (`.gitignore`d), and runs on pure Python 3 standard library + SQLite.
- **Unrestricted by design:** Commercial enterprise tools lock down USB debugging, app installs, Wi-Fi changes, and accounts. `AreoleDPC` actively calls `DevicePolicyManager.clearUserRestriction()` on all 12 common lockouts so you always stay the boss of your hardware.
- **Safe, reversible debloating:** Hides retail/carrier bloat packages with `setApplicationHidden()` (no `/system` partition surgery, so OS security updates continue working) while carefully leaving core utilities and everyday essentials—**Dialer, Messages, Camera, Play Store, Google Drive, YouTube Music, YouTube, and Google Photos**—completely untouched. While management is active you can unhide anything; when you later deprovision, hidden packages are converted to permanent user-0 uninstalls so the clean phone survives the exit (see *Non-Destructive Deprovisioning* below).
- **Calm status bar out of the box:** Optional **Notifications Off by Default** denies `POST_NOTIFICATIONS` on non-core apps on Android 13–16+, leaving calls, SMS, alarms, and system alerts intact.
- **Non-destructive exit:** Because first-boot **Device Owner** (`PROVISIONING_MODE_FULLY_MANAGED_DEVICE`) lets the controller call `clearDeviceOwnerApp()`, you can revoke management anytime from the phone app or Web UI without factory-resetting your personal data.
- **Optional IP camera companion:** Built-in, SHA-256-verified fetch & `PackageInstaller` delivery for the open-source [Thingino Android App (`v0.6.0`)](https://github.com/thingino/thingino-app).

---

## Copy-Paste Setup Prompt (`agy`, `codex`, `hermes`, `claude`)

Want a coding assistant to set this up with you step-by-step and watch the live HTTPS tunnel while you scan the QR code on your phone? Clone or open a terminal in this folder and paste the block below directly into **`agy`**, **`codex`**, **`hermes`**, or **`claude`**:

```text
Help me clone, build, and run AREOLE-DPC-HWTF from GitHub on this machine so I can
provision and debloat an Android phone using 6-tap QR enrollment (or ADB fallback).

Follow these exact steps and explain what each command does as we go:
1. Check OS packages and ensure OpenJDK 17/21, python3, curl, unzip, and qrencode are installed.
2. If not already inside the repo, clone:
   git clone https://github.com/chieftechnicalwizard/AREOLE-DPC-HWTF.git && cd AREOLE-DPC-HWTF
3. Run the bootstrap script with HTTPS tunnel and optional Thingino support:
   chmod +x setup.sh build_dpc.sh server.py
   ./setup.sh --with-tunnel --with-thingino
4. Verify static/areole-dpc.apk built cleanly and read out the signing certificate
   URL-safe SHA-256 checksum using apksigner.
5. Launch the provisioning server with an ephemeral HTTPS tunnel:
   python3 server.py --tunnel
6. Watch the printed Web Console URL (http://127.0.0.1:8780) and HTTPS Tunnel URL
   (https://*.trycloudflare.com). Help me:
   - Pick "First-Boot 6-Tap Device Owner" in the Web UI
   - Fill optional Wi-Fi SSID/password if I want the phone to auto-join Wi-Fi
   - Choose my bloatware / notification-mute / Thingino checkboxes
   - Walk me through factory-reset Welcome screen -> 6 taps -> scan QR -> verify
     device check-in on the "Enrolled Devices" tab
   - Verify no secrets or keystores were committed if I inspect git status.
```

---

## Quick Start (Self-Hosting in 3 Minutes)

### Prerequisites
- Linux host (**Debian / Ubuntu / Mint**, **Arch / Omarchy / Manjaro**, **Fedora / RHEL / Rocky / Alma**, **openSUSE**, **Alpine**, **Void**, or **NixOS**) with **Java JDK 17+** (`javac`/`keytool`), **Python 3.10+**, **`unzip`**, **`zip`**, **`curl`**, and **`qrencode`** (optional, for sharp SVG QR codes in the browser).
- `./setup.sh` auto-detects `apt-get`, `pacman`, `dnf`, `zypper`, `apk`, and `xbps-install` to install missing dependencies automatically (or pass `--skip-deps` if you manage tools yourself).
- An Android phone (**Android 9–16+** tested; bloat preset tuned specifically around Motorola retail/carrier builds such as Moto G Power 2026 while safe on any Android device).

<details>
<summary>Manual per-distribution dependency install commands (optional)</summary>

| Distribution | Package Manager Command |
| :--- | :--- |
| **Debian / Ubuntu / Pop!_OS / Mint** | `sudo apt-get update && sudo apt-get install -y python3 qrencode curl unzip zip openjdk-21-jdk-headless` |
| **Arch Linux / Omarchy / Manjaro** | `sudo pacman -Sy --needed python qrencode curl unzip zip jdk21-openjdk` |
| **Fedora / RHEL / Rocky / Alma** | `sudo dnf install -y python3 qrencode curl unzip zip java-21-openjdk-devel` |
| **openSUSE (Tumbleweed / Leap)** | `sudo zypper install python3 qrencode curl unzip zip java-21-openjdk-devel` |
| **Alpine Linux** | `sudo apk add python3 libqrencode-tools curl unzip zip openjdk21-jdk bash` |
| **Void Linux** | `sudo xbps-install -Sy python3 qrencode curl unzip zip openjdk21` |
| **NixOS / Nix** | `nix-shell -p openjdk21 python3 qrencode curl unzip zip --run './setup.sh --skip-deps --with-tunnel --with-thingino'` |

</details>

### 1. Clone & Bootstrap

```bash
git clone https://github.com/chieftechnicalwizard/AREOLE-DPC-HWTF.git
cd AREOLE-DPC-HWTF

chmod +x setup.sh build_dpc.sh server.py
./setup.sh --with-tunnel --with-thingino
```

What `./setup.sh` does for you:
1. Checks/installs Java JDK, `qrencode`, `curl`, `unzip`, `zip`, and Python 3.
2. Downloads official Google Android `commandlinetools` (`platforms;android-35`, `build-tools;35.0.0`, and `platform-tools` **`adb` 37.x**—which fixes Wireless ADB pairing failures seen in older OS-packaged `adb 34.x` builds) into `~/.local/share/android-sdk/`.
3. Generates your private `.keystore` + random 24-character password inside `keystore/` (never tracked by git) and compiles `android_dpc/` into `static/areole-dpc.apk`.
4. With `--with-tunnel`, fetches `cloudflared` into `~/.local/bin/cloudflared`.
5. With `--with-thingino`, downloads `thingino-android.apk` `v0.6.0` into `static/apps/` and checks its exact SHA-256 digest (`bf4e9181d282f595dd40caf0a8d8b26d16f34135ab96e8acc87f89fde96a81af`).

### 2. Start the Self-Hosted Server + HTTPS Tunnel

Why `--tunnel`? Android 14, 15, and 16 Setup Wizard (`ManagedProvisioning`) **refuses plain `http://` download URLs** during 6-tap QR provisioning. Adding `--tunnel` opens a temporary, zero-account `trycloudflare.com` HTTPS endpoint pointing at your local server—and **`server.py` automatically blocks admin/QR/ADB endpoints with HTTP `403` from that public tunnel** so only the phone APK fetch and device check-in routes are reachable outside your LAN.

```bash
python3 server.py --tunnel
```

Open your browser locally to **`http://127.0.0.1:8780`**.

---

## Option B: Containerized Self-Hosting (Docker / Podman)

Prefer not to install Java JDK, `qrencode`, or the Android SDK onto your host OS? Run everything isolated inside one reproducible container using [`Dockerfile`](Dockerfile), [`docker-entrypoint.sh`](docker-entrypoint.sh), and [`compose.yaml`](compose.yaml).

**Zero baked secrets:** No signing keys or APKs are built into the container image. On first boot, `docker-entrypoint.sh` generates your own private RSA-2048 keystore inside the persistent `/var/lib/areole` volume, signs `areole-dpc.apk`, and reuses that same identity across future restarts or container upgrades.

### One-Command Compose Launch

```bash
git clone https://github.com/chieftechnicalwizard/AREOLE-DPC-HWTF.git
cd AREOLE-DPC-HWTF

docker compose up -d --build
docker compose logs -f
```

Open **`http://127.0.0.1:8780`** in your browser. Look in `docker compose logs -f` for the live `https://*.trycloudflare.com` tunnel URL (or check the Server URL dropdown in the Web UI).

### Optional Container Settings (`compose.yaml` or `docker run`)

| Environment Variable | Default | Purpose |
| :--- | :--- | :--- |
| `AREOLE_MDM_PORT` | `8780` | Web console & APK server port |
| `ENABLE_TUNNEL` | `1` | Start an ephemeral Cloudflare HTTPS Quick Tunnel (`0` = LAN / ADB only) |
| `INSTALL_THINGINO` | `0` | Pre-download & SHA-256 verify Thingino `v0.6.0` on startup (`1` = enable) |
| `REBUILD_APK` | `0` | Force recompiling `areole-dpc.apk` with the existing persistent keystore (`1` = rebuild) |

**Direct `docker run` / `podman run` equivalent:**

```bash
docker build -t areole-dpc-hwtf .
docker run -d --name areole-dpc \
  --network host \
  -e ENABLE_TUNNEL=1 \
  -v areole_state:/var/lib/areole \
  areole-dpc-hwtf
```

> **Networking note:** `network_mode: host` (default in [`compose.yaml`](compose.yaml)) lets `server.py` detect your real LAN IP addresses and reach Android **Wireless Debugging** on your subnet directly. On macOS or Windows Docker Desktop, comment out `network_mode: host` in `compose.yaml` and uncomment `ports: ["127.0.0.1:8780:8780"]` (6-tap QR via the `--tunnel` HTTPS URL and `/setup` work identically!).

---

## Option C: Public Multi-User Mode (`--public`)

Run **one deployment for many strangers** — each visitor provisions and debloats *their own* phone without anyone being able to see or touch anyone else's device, and without creating accounts. The default self-hosted behavior (full console, LAN discovery, ADB tab) stays exactly as before; public mode is opt-in.

```bash
AREOLE_PUBLIC=1 AREOLE_PUBLIC_BASE_URL=https://areole.example.com python3 server.py --public
# or: python3 server.py --public --public-base-url https://areole.example.com
# containers: ENABLE_PUBLIC=1 (+ AREOLE_PUBLIC_BASE_URL) in compose.yaml
```

### How isolation works

| Credential | Holder | Grants |
| :--- | :--- | :--- |
| `areole_session` cookie | Each visitor's browser (auto-created, `HttpOnly`/`SameSite=Lax`, `Secure` behind HTTPS) | A private ~48h session: QR generation + visibility/control of **only** that session's devices |
| `enrollment_token` | Each enrolled phone (embedded in its QR, sent on every check-in; the server keeps the token only for the life of its session, then purges it) | That one device's check-in — first check-in binds token→device, and a token can never claim a second device or another session's device |

Concretely: `/api/status`, `/api/device/command`, and `/api/device/delete` are scoped to the session's own devices (cross-session targets return `404`, revealing nothing); `/api/device/checkin` requires a valid token; `/api/qr` always points at your canonical public origin; the ADB tab is disabled (it drives the *server host's* adb daemon and cannot be multi-tenant). Per-IP rate limits apply to check-ins, QR generation, and session creation.

### The lifecycle ends with the corporate stuff gone

When a session expires (default **48h**; the expected flow is under a day), the server automatically queues **`DEPROVISION_KEEP_PERSONAL`** for each of its devices. Phones enrolled in public mode run a light built-in background check-in (~every 15 min, set only when the QR carried `auto_retire`) so that final *remove-the-controller* command is delivered even if the user never reopens the app. After a grace window (default 24h) every trace is purged: devices, app inventories, commands, tokens. Users can always leave earlier with the in-app **Deprovision & Remove Controller** button, which works fully offline.

### Deployment requirements

- **Your own HTTPS reverse proxy in front** (Android 14–16 Setup Wizard rejects plain `http://` download URLs). It must forward `X-Forwarded-Proto` so the session cookie gets its `Secure` flag. Caddy example:

  ```
  areole.example.com {
      reverse_proxy 127.0.0.1:8780
  }
  ```

- Set `AREOLE_PUBLIC_BASE_URL` so QR payloads carry your canonical origin (otherwise it is derived from each request's `Host` + `X-Forwarded-Proto`).
- Tuning: `AREOLE_SESSION_TTL` (hours, default 48) and `AREOLE_RETIRE_GRACE` (hours after expiry before the hard purge, default 24).
- Remember: with one signing keystore you are the Device Owner identity strangers' phones trust — keep `keystore/` safe and expect abuse-handling responsibilities (e.g. someone provisioning a stolen phone).

---

## Step-by-Step: 6-Tap QR Phone Enrollment

1. **Choose Options in the Web UI (`http://127.0.0.1:8780`)**
   - **Template Type:** `Android 9.0–16+ (Signature Checksum — Recommended)`
   - **Provisioning Mode:** `First-Boot 6-Tap Device Owner (Self-Clear Without Wipe)`
   - **Server URL:** Select the `https://*.trycloudflare.com` tunnel URL at the top of the dropdown.
   - **Profile Label / Wi-Fi (Optional):** Enter a label (`Owner` by default). Filling your Wi-Fi SSID & password inside the QR payload lets the phone connect automatically without typing a password on glass!
   - **Toggles:** Check **Strip OEM & Carrier Bloatware**, **Notifications Off by Default**, and optionally **Install Thingino App (v0.6.0)**.
2. **Trigger the Hidden QR Scanner on Android**
   - Power on a factory-reset Android phone and stay on the very first **Welcome / Hi there** screen.
   - Tap empty background space on that Welcome screen **6 times rapidly** until the QR reader opens.
   - Point the phone at the QR code on your computer monitor.
3. **Watch the Provisioning Handshake Finish**
   - Android joins Wi-Fi, downloads `areole-dpc.apk` over HTTPS, verifies the `PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM`, creates Device Owner scope, applies bloat-hiding + notification silence, and walks cleanly through consent → OEM privacy → Google Services straight to the home screen:

| 1. Accept Device Owner | 2. OEM Privacy & Telemetry | 3. Google Services | 4. Enrolled & Debloated (`v1.0.2`) |
| :---: | :---: | :---: | :---: |
| ![Accept Device Owner](docs/screenshots/01_accept_device_owner.jpg) | ![Motorola Privacy & Security](docs/screenshots/02_moto_privacy_security.jpg) | ![Google Services](docs/screenshots/03_google_services.jpg) | ![AreoleDPC Enrolled](docs/screenshots/04_areole_dpc_enrolled.png) |

   *(Real hardware capture on a factory-reset Moto G Power 2026 / Android 16 — `DEVICE_OWNER` bound with `0` restrictions, `39` bloat packages hidden on first boot, and zero Setup Wizard crashes.)*

   > **Friendly Reminder on Screen 1 (*"This device isn't private"*):** Android always displays that standard enterprise disclaimer during Device Owner setup. **In this case, YOU are the organization and the IT admin** — your phone is being enrolled exclusively into your own self-hosted, privately signed `AreoleDPC` controller with zero cloud accounts or third-party oversight. All `UserManager` restrictions are cleared immediately, and you can tap **Deprovision & Remove Controller (Keep Personal)** anytime to remove management without wiping your personal data.

4. **Already Set Up Without Factory Resetting? (ADB & BYOD Modes)**
   - Visit `<server_url>/setup` on your phone browser to install `areole-dpc.apk` and create a removable **Work Profile**, OR plug in USB / pair **Wireless Debugging** in Tab 3 (`USB / Wireless ADB Control`) to run one-click user-0 debloating, notification muting, or optional Thingino installation without resetting at all.

### Troubleshooting: Setup Wizard crash-loops after scanning the QR

> **Fixed in `v1.0.2+` (`3e59b14`):** On Motorola Android 16 devices (including Moto G Power 2026 / retail & Tracfone builds), older `v1.0.1` APKs triggered an *"Android setup keeps stopping"* loop right after *"Registering device" → "Checking for updates"* because `MOTO_BLOAT_PACKAGES` hid `com.motorola.setup` (`/system_ext/priv-app/SetupWizardExt/SetupWizardExt.apk`), which hosts `res/raw/wizard_script_post_dpm_user_flow_*.xml` for `WizardManagerActivity`. `com.motorola.setup` has been removed from the preset and `DpcConfig.setPackagesHidden()` now refuses to hide setup-wizard packages while `user_setup_complete == 0` (verified **0 crashes** across retail Moto G Power 2026 Android 16 units). If you upgraded an existing Docker volume from `v1.0.1`, start once with `REBUILD_APK=1` so the container recompiles the updated APK.

**Fallback for older APKs or unusual GMS/carrier builds:** If a different OEM/carrier build ever stalls during post-DPM finalization (for example, when Google's **Android Device Policy** `com.google.android.apps.work.clouddpc` intercepts `ROLE_HOLDER_PROVISION_FINALIZATION`), **provisioning itself has already succeeded** — Device Owner is bound, debloat is applied, and the device checks into your console. Press Back/Close to reach the launcher, then run over USB ADB to clear any stuck OOBE state:

```bash
adb shell pm disable-user --user 0 com.google.android.apps.work.clouddpc
adb shell settings put secure user_setup_complete 1
adb shell settings put global device_provisioned 1
```

Then reboot once to refresh launcher icons and verify `Role: DEVICE_OWNER` in the **Enrolled Devices** tab. Carrier-bloat package names vary per firmware — hide any stragglers manually from the **App Inventory drawer**; packages marked `non-disable` by the OEM (e.g. `com.amazon.appmanager` or `com.motorola.installer` on some builds) cannot be removed without root.

---

## How the Code Works (Architecture & Teaching Guide)

Every source file is heavily commented so you can audit and learn the exact Android internals:

| File | Purpose & Key Android Mechanics Taught |
| :--- | :--- |
| [`server.py`](server.py) | Pure Python stdlib HTTP server, dynamic SDK/`apksigner`/`adb` resolver, URL-safe unpadded Base64 SHA-256 cert digest builder, `do_HEAD()` for Android 14–16 `ManagedProvisioning`, `cloudflared` HTTPS quick-tunnel runner with `403` admin isolation, SQLite command queue, and ADB controller. |
| [`static/index.html`](static/index.html) | Self-contained 3-tab browser console: live QR JSON generator + SVG renderer, Enrolled Devices & App Inventory hide/restore drawer, and Wireless/USB ADB controls. |
| [`build_dpc.sh`](build_dpc.sh) | Builds `areole-dpc.apk` from raw Java & XML without Gradle bloat: `aapt2 compile` -> `aapt2 link` -> `javac --release 11` -> `d8` DEX compiler -> `zip` + `zipalign` -> `apksigner` v1/v2/v3 APK signing with a local auto-generated PKCS12 keystore. |
| [`setup.sh`](setup.sh) | Multi-distro host bootstrapper (`apt-get`, `pacman`, `dnf`, `zypper`, `apk`, `xbps-install`, `--skip-deps`) that installs OS tools, official Google Android SDK `android-35` + `build-tools;35.0.0` + `platform-tools` 37.x, builds the APK, and optionally caches `cloudflared` and SHA-256-verified Thingino `v0.6.0`. |
| [`Dockerfile`](Dockerfile) | Multi-stage-clean Ubuntu 24.04 container packaging OpenJDK 21, Python 3, `qrencode`, `iproute2`, Android SDK 35 + `adb` 37+, and `cloudflared` under non-root UID `10001`. |
| [`docker-entrypoint.sh`](docker-entrypoint.sh) | First-boot container initializer that prints `banner.ans`, generates a persistent keystore inside `/var/lib/areole`, compiles `areole-dpc.apk`, verifies optional Thingino, and `exec`s `server.py`. |
| [`compose.yaml`](compose.yaml) | Ready-to-run Compose stack with `network_mode: host`, persistent `areole_state` volume, and documented bridged/USB options. |
| [`android_dpc/AndroidManifest.xml`](android_dpc/AndroidManifest.xml) | Declares the required `BIND_DEVICE_ADMIN` activities (`GET_PROVISIONING_MODE`, `ADMIN_POLICY_COMPLIANCE`) and `DeviceAdminReceiver` (`PROFILE_PROVISIONING_COMPLETE`, `BOOT_COMPLETED`). |
| [`GetProvisioningModeActivity.java`](android_dpc/src/com/areole/dpc/GetProvisioningModeActivity.java) | Step 1 of Setup Wizard handshake: reads `PROVISIONING_ADMIN_EXTRAS_BUNDLE` from the QR code, persists your server URL and flags, and selects Device Owner or Managed Profile mode. |
| [`PolicyComplianceActivity.java`](android_dpc/src/com/areole/dpc/PolicyComplianceActivity.java) | Step 2 of Setup Wizard handshake: applies `clearUserRestriction()`, hides bloatware immediately, fires background server sync, and returns `Activity.RESULT_OK` so setup completes. |
| [`AreoleDeviceAdminReceiver.java`](android_dpc/src/com/areole/dpc/AreoleDeviceAdminReceiver.java) | Lifecycle broadcast receiver using `goAsync()` to resync config at provisioning completion and across `BOOT_COMPLETED`. |
| [`DpcConfig.java`](android_dpc/src/com/areole/dpc/DpcConfig.java) | Core engine: unrestricted owner profile labeling, `setApplicationHidden()` debloat engine, Android 13+ `POST_NOTIFICATIONS` default silencer, `PackageInstaller` APK streamer for Thingino, app inventory collector, and non-destructive `clearDeviceOwnerApp()` unenrollment. |
| [`MainActivity.java`](android_dpc/src/com/areole/dpc/MainActivity.java) | Zero-dependency programmatic Android UI displaying device role, 15-second live command poller, one-tap debloat/notification controls, Thingino installer, and "Deprovision & Remove Controller (Keep Personal)" button. |
| [`banner.ans`](banner.ans) | 256-color ANSI art desert cacti scene printed by CLI scripts. |

### Provisioning Flow Diagram

```text
  [Factory Reset Phone]
           |  (6 taps on Welcome screen)
           v
  [Android ManagedProvisioning] -- scans QR JSON --> { DOWNLOAD_LOCATION, SIGNATURE_CHECKSUM, EXTRAS }
           |
           |-- HTTP HEAD + GET /apk/areole-dpc.apk (HTTPS Tunnel) --> [server.py]
           |
           |-- Verifies APK v2/v3 Cert SHA-256 == SIGNATURE_CHECKSUM
           |-- Installs AreoleDPC
           |-- Launches GetProvisioningModeActivity  --> picks DEVICE_OWNER
           |-- Launches PolicyComplianceActivity     --> clears restrictions, hides bloat, RESULT_OK
           '-- Fires AreoleDeviceAdminReceiver       --> syncs POST /api/device/checkin
```

---

## Security & Privacy Checklist (Secret-Free by Design)

- Signing keystores (`keystore/`, `*.jks`, `*.keystore`, `.storepass`), compiled APKs (`static/*.apk`, `static/apps/`), runtime SQLite databases (`data/`), and `tunnel_url.txt` are **all listed in [`.gitignore`](.gitignore)**.
- If you fork or publish your own copy, keep your `keystore/` private so nobody else can sign APKs matching your QR certificate checksum.
- When exposed with `--tunnel`, `server.py` checks proxy headers (`CF-Connecting-IP`, `CF-Ray`, `Host: *.trycloudflare.com`) and blocks access to `/`, `/api/qr`, `/api/status`, `/api/device/command`, and `/api/adb/*` with **HTTP `403`**.

---

## Non-Destructive Deprovisioning (Leaving Cleanly)

Want `AreoleDPC` completely gone after your phone is debloated and tuned?

1. **In the Android app (`Areole Provisioner DPC`)** or **in Tab 2 of the Web UI**, choose **Deprovision & Remove Controller (Keep Personal)**.
2. Under **Device Owner**, `AreoleDPC` does two things before calling `dpm.clearDeviceOwnerApp("com.areole.dpc")`: it clears all `UserManager` restrictions, and it **converts every hidden bloat package into a permanent user-0 uninstall** (`PackageInstaller`, identical in effect to the ADB path's `pm uninstall -k --user 0`). This step exists because Android otherwise *restores* every app an admin hid with `setApplicationHidden()` the moment that admin is removed — silently undoing your debloat. User-0 uninstalls are plain PackageManager state: they survive management removal and reboots, the APKs stay on `/system` (so OS security updates and a factory reset can always restore them), and your personal apps, accounts, and photos are never touched. Management then ends immediately and you can uninstall the DPC app normally afterwards.
3. Under a **BYOD Work Profile**, it cleanly deletes only the Work container while keeping your main personal profile safe.

> **OTA, Persistence & Anti-Carrier Guide:** On Android 16 retail Motorola builds, clearing Device Owner reverts `setApplicationHidden()` unless packages are uninstalled for user 0 (`pm uninstall --user 0`), and a few OEM stubs (notably `com.motorola.installer` and `com.tracfone.preload.accountservices`) are framework-protected as `non-disable`. See [`docs/OTA_REBLOAT_FINDINGS.md`](docs/OTA_REBLOAT_FINDINGS.md) for the real-hardware OTA timeline and **[Keeping Self-Signed Device Owner Active (Persistence, Reboots & Normal Development Gist)](https://gist.github.com/chieftechnicalwizard/dfeb6546ba0efdd119349f0036feaf46)** for why keeping your persistent self-signed keystore (`~/AREOLE-DPC-HWTF/keystore/`) active is safe across laptop reboots and ideal for everyday development.

---

## Sponsors & Donations

Sponsorship and donations support Shekinah Shine maintenance, sanctuary groundskeeping, 24/7 broadcast infrastructure, and open-source development.

<p>
  <a href="https://www.shekinahshine.org/?donate=paypal"><img src="docs/badges/paypal-donate-pill.svg" alt="Donate via PayPal" height="24" align="absmiddle" /></a> &nbsp;·&nbsp;
  <a href="https://www.shekinahshine.org/?donate=paypal"><img src="docs/badges/icon-paypal.svg" width="16" height="16" align="absmiddle" alt="" /> PayPal Donate (Shekinah Shine)</a> &nbsp;·&nbsp;
  <a href="https://www.shekinahshine.org/?donate=cashapp"><img src="docs/badges/icon-cashapp.svg" width="16" height="16" align="absmiddle" alt="" /> Cash App</a> &nbsp;·&nbsp;
  <a href="https://www.shekinahshine.org/?donate=venmo"><img src="docs/badges/icon-venmo.svg" width="16" height="16" align="absmiddle" alt="" /> Venmo</a> &nbsp;·&nbsp;
  <a href="https://github.com/sponsors/chieftechnicalwizard"><img src="docs/badges/icon-github-sponsors.svg" width="16" height="16" align="absmiddle" alt="" /> GitHub Sponsors</a> &nbsp;·&nbsp;
  <a href="https://www.shekinahshine.org/"><img src="docs/badges/icon-shekinah.svg" width="16" height="16" align="absmiddle" alt="" /> Shekinah Shine Website</a>
</p>

---

## License

Apache-2.0 — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

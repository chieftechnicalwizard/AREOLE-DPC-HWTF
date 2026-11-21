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

<a href="https://www.shekinahshine.org/?donate=paypal"><img src="docs/badges/paypal-donate-pill.svg" alt="Donate via PayPal" height="22" /></a>

**Own your phone, silence the adware, and keep zero lock-in.**

`AREOLE-DPC-HWTF` ("How Wait... That's Free?!") is a self-hosted, single-machine Android Provisioning Controller (DPC) and HTTP/QR console. Instead of handing management of a brand-new or freshly reset Android phone to a third-party cloud vendor—or settling for a drawer full of preloaded carrier installers, silent promo downloaders, and noisy notification popups—you run a tiny local Python server + compile your own signed Android DPC APK in about two minutes.

Scan one QR code on the factory **Welcome** screen (tap empty space **6 times**), let Android enroll your own controller, strip bloatware across the system cleanly, optionally silence non-core app notifications by default, optionally sideload companion tools like **Thingino (`v0.6.0`)**, and whenever you are done, tap **Deprovision & Remove Controller** to drop ownership without wiping a single photo, message, or setting.

---

## Why People Use This

- **Zero accounts, zero cloud fees, zero telemetry:** Everything compiles locally, signs with a freshly generated private keystore on your own disk (`.gitignore`d), and runs on pure Python 3 standard library + SQLite.
- **Unrestricted by design:** Commercial enterprise tools lock down USB debugging, app installs, Wi-Fi changes, and accounts. `AreoleDPC` actively calls `DevicePolicyManager.clearUserRestriction()` on all 12 common lockouts so you always stay the boss of your hardware.
- **Safe, reversible debloating:** Hides retail/carrier bloat packages with `setApplicationHidden()` (no `/system` partition surgery, so OS security updates continue working) while carefully leaving core utilities and everyday essentials—**Dialer, Messages, Camera, Play Store, Google Drive, YouTube Music, YouTube, and Google Photos**—completely untouched.
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
   - Android joins Wi-Fi, downloads `areole-dpc.apk` over HTTPS, verifies the `PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM`, creates Device Owner scope, applies bloat-hiding + notification silence, and returns to the desktop ready to use!
4. **Already Set Up Without Factory Resetting? (ADB & BYOD Modes)**
   - Visit `<server_url>/setup` on your phone browser to install `areole-dpc.apk` and create a removable **Work Profile**, OR plug in USB / pair **Wireless Debugging** in Tab 3 (`USB / Wireless ADB Control`) to run one-click user-0 debloating, notification muting, or optional Thingino installation without resetting at all.

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
2. Under **Device Owner**, `AreoleDPC` ensures all `UserManager` restrictions are cleared and calls `dpm.clearDeviceOwnerApp("com.areole.dpc")`. Management ends immediately—your personal apps, accounts, photos, and hidden bloatware state stay untouched, and you can uninstall the DPC app normally afterwards.
3. Under a **BYOD Work Profile**, it cleanly deletes only the Work container while keeping your main personal profile safe.

> **OTA & Post-Deprovision Rebloat Note:** On Android 16 retail Motorola builds, clearing Device Owner reverts `setApplicationHidden()` unless packages are uninstalled for user 0 (`pm uninstall --user 0`), and a few OEM stubs (notably `com.motorola.installer` and `com.tracfone.preload.accountservices`) are framework-protected as `non-disable`. See [`docs/OTA_REBLOAT_FINDINGS.md`](docs/OTA_REBLOAT_FINDINGS.md) for the full real-hardware update timeline (`W1WEOS36.48-22-3-3-4-3` ➔ `W1WEOS36.48-22-3-3-4-7`), empirical 44/44 post-OTA persistence verification, and DNS/Device-Owner mitigation notes.

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

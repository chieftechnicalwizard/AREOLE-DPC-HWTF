#!/usr/bin/env bash
# ==============================================================================
# docker-entrypoint.sh — Container Bootstrapping & Signal-Safe Process Runner
#
# What happens each time your container starts:
#   1. Shows the 256-color Trichocereus banner in container logs (`docker logs`).
#   2. Checks whether `/var/lib/areole/data/areole-dpc.apk` already exists inside
#      your persistent volume. On first boot (or when REBUILD_APK=1), it creates
#      a unique private RSA-2048 keystore inside `/var/lib/areole/keystore/` and
#      compiles + signs `areole-dpc.apk`. Subsequent restarts reuse the same key
#      so already-enrolled phones & saved QR checksums continue matching!
#   3. Optionally caches & SHA-256-verifies Thingino v0.6.0 (`INSTALL_THINGINO=1`).
#   4. Launches `server.py` with `exec` so Docker/Podman signals (SIGTERM/SIGINT)
#      cleanly shut down both the Python server and any Cloudflare tunnel child.
# ==============================================================================
set -euo pipefail

mkdir -p "$AREOLE_KEYSTORE_DIR" "$AREOLE_DATA_DIR" "$AREOLE_APPS_DIR"

if [ -f /app/banner.ans ]; then
    cat /app/banner.ans
    echo ""
fi

# 1. Compile & sign AreoleDPC APK on first boot (or when REBUILD_APK=1)
if [ "${REBUILD_APK:-0}" = "1" ] || [ ! -f "$AREOLE_APK_PATH" ]; then
    echo "[*] Building & signing AreoleDPC APK into persistent volume ($AREOLE_APK_PATH)..."
    /app/build_dpc.sh
else
    echo "[*] Reusing existing signed APK from persistent volume: $AREOLE_APK_PATH"
fi

# 2. Optional Thingino camera viewer v0.6.0 pre-fetch (SHA-256 verified)
if [ "${INSTALL_THINGINO:-0}" = "1" ]; then
    THINGINO_DST="$AREOLE_APPS_DIR/thingino-android.apk"
    THINGINO_SHA="bf4e9181d282f595dd40caf0a8d8b26d16f34135ab96e8acc87f89fde96a81af"
    if [ ! -f "$THINGINO_DST" ]; then
        echo "[*] Downloading official Thingino Android app v0.6.0..."
        curl -fsSL "https://github.com/thingino/thingino-app/releases/download/v0.6.0/thingino-android.apk" -o "$THINGINO_DST"
    fi
    ACTUAL_SHA="$(sha256sum "$THINGINO_DST" | awk '{print $1}')"
    if [ "$ACTUAL_SHA" != "$THINGINO_SHA" ]; then
        echo "[!] SHA-256 mismatch for thingino-android.apk ($ACTUAL_SHA != $THINGINO_SHA)" >&2
        rm -f "$THINGINO_DST"
        exit 1
    fi
    echo "[+] Verified thingino-android.apk (SHA-256 OK)"
fi

# 3. Assemble server flags cleanly and hand over PID 1 via `exec`
ARGS=("--host" "$AREOLE_MDM_HOST" "--port" "$AREOLE_MDM_PORT" "--no-banner")
if [ "${ENABLE_TUNNEL:-1}" = "1" ]; then
    ARGS+=("--tunnel")
fi
# Public multi-user mode: session cookies + token-bound devices + auto-deprovision
# on session expiry; ADB controls disabled. Put the site behind your own HTTPS
# reverse proxy and set AREOLE_PUBLIC_BASE_URL (server.py also reads
# AREOLE_SESSION_TTL / AREOLE_RETIRE_GRACE directly from the environment).
if [ "${ENABLE_PUBLIC:-0}" = "1" ]; then
    ARGS+=("--public")
    echo "[*] Public multi-user mode enabled (put this behind an HTTPS reverse proxy!)"
fi

exec python3 -u /app/server.py "${ARGS[@]}" "$@"

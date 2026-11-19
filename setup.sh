#!/usr/bin/env bash
# ==============================================================================
# setup.sh — One-command bootstrap for AREOLE-DPC-HWTF
#
# Installs prerequisites (Debian/Ubuntu), downloads Google's standalone Android
# commandlinetools + SDK 35, compiles & signs AreoleDPC, and optionally fetches
# cloudflared (for trusted HTTPS 6-tap QR provisioning) and thingino-android.apk.
#
# Usage:
#   ./setup.sh                  # Install SDK + build APK
#   ./setup.sh --with-tunnel    # Also install cloudflared quick-tunnel binary
#   ./setup.sh --with-thingino  # Also download & SHA-256 verify Thingino v0.6.0
#   ./setup.sh --start          # Start server.py after building
#   ./setup.sh --start-tunnel   # Start server.py with managed HTTPS tunnel
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
SDK_DIR="${ANDROID_HOME:-$HOME/.local/share/android-sdk}"
LOCAL_BIN="$HOME/.local/bin"
WITH_TUNNEL=0
WITH_THINGINO=0
START_MODE=""

for arg in "$@"; do
    case "$arg" in
        --with-tunnel) WITH_TUNNEL=1 ;;
        --with-thingino) WITH_THINGINO=1 ;;
        --start) START_MODE="plain" ;;
        --start-tunnel) WITH_TUNNEL=1; START_MODE="tunnel" ;;
        -h|--help)
            sed -n '2,17p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown flag: $arg" >&2
            exit 1
            ;;
    esac
done

[ -f "$ROOT_DIR/banner.ans" ] && cat "$ROOT_DIR/banner.ans"
echo ""

# 1. OS packages (apt on Debian/Ubuntu; non-apt distros print required tools)
if command -v apt-get >/dev/null 2>&1; then
    MISSING=()
    for cmd in python3 qrencode curl unzip zip javac; do
        command -v "$cmd" >/dev/null 2>&1 || MISSING+=("$cmd")
    done
    if [ "${#MISSING[@]}" -gt 0 ]; then
        echo "[*] Installing system packages (needs sudo): ${MISSING[*]}"
        PKGS=()
        for m in "${MISSING[@]}"; do
            if [ "$m" = "javac" ]; then
                PKGS+=("openjdk-21-jdk-headless")
            else
                PKGS+=("$m")
            fi
        done
        sudo apt-get update -qq
        sudo apt-get install -y "${PKGS[@]}"
    fi
else
    for cmd in python3 qrencode curl unzip zip javac keytool; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            echo "Missing required tool: $cmd. Please install it with your package manager." >&2
            exit 1
        fi
    done
fi

# 2. Android SDK 35 + build-tools + official platform-tools (adb)
# Note: Google's standalone platform-tools adb (35+/37+) avoids the Wireless ADB
# pairing client bug present in older distro packages.
if [ ! -f "$SDK_DIR/platforms/android-35/android.jar" ] || [ ! -x "$SDK_DIR/platform-tools/adb" ]; then
    echo "[*] Installing Android SDK 35, build-tools 35.0.0, and platform-tools into $SDK_DIR..."
    mkdir -p "$SDK_DIR/cmdline-tools"
    if [ ! -x "$SDK_DIR/cmdline-tools/latest/bin/sdkmanager" ]; then
        TMP_ZIP="$(mktemp --suffix=.zip)"
        curl -fL "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip" -o "$TMP_ZIP"
        unzip -q -o "$TMP_ZIP" -d "$SDK_DIR/cmdline-tools"
        rm -rf "$SDK_DIR/cmdline-tools/latest"
        mv "$SDK_DIR/cmdline-tools/cmdline-tools" "$SDK_DIR/cmdline-tools/latest"
        rm -f "$TMP_ZIP"
    fi
    yes | "$SDK_DIR/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$SDK_DIR" \
        "platforms;android-35" "build-tools;35.0.0" "platform-tools" >/dev/null
fi

# 3. Compile & sign AreoleDPC APK
chmod +x "$ROOT_DIR/build_dpc.sh"
"$ROOT_DIR/build_dpc.sh"

# 4. Optional Cloudflare Quick Tunnel binary for trusted HTTPS 6-tap QR provisioning
if [ "$WITH_TUNNEL" -eq 1 ] && ! command -v cloudflared >/dev/null 2>&1 && [ ! -x "$LOCAL_BIN/cloudflared" ]; then
    mkdir -p "$LOCAL_BIN"
    ARCH="$(uname -m)"
    case "$ARCH" in
        x86_64|amd64) CF_ARCH="amd64" ;;
        aarch64|arm64) CF_ARCH="arm64" ;;
        *) echo "Unsupported arch for auto cloudflared download: $ARCH" >&2; exit 1 ;;
    esac
    echo "[*] Downloading cloudflared ($CF_ARCH) to $LOCAL_BIN/cloudflared..."
    curl -fL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" -o "$LOCAL_BIN/cloudflared"
    chmod +x "$LOCAL_BIN/cloudflared"
fi

# 5. Optional Thingino companion app (v0.6.0, SHA-256 pinned)
if [ "$WITH_THINGINO" -eq 1 ]; then
    THINGINO_DST="$ROOT_DIR/static/apps/thingino-android.apk"
    THINGINO_SHA="bf4e9181d282f595dd40caf0a8d8b26d16f34135ab96e8acc87f89fde96a81af"
    mkdir -p "$(dirname "$THINGINO_DST")"
    if [ ! -f "$THINGINO_DST" ]; then
        echo "[*] Downloading official Thingino Android app v0.6.0..."
        curl -fL "https://github.com/thingino/thingino-app/releases/download/v0.6.0/thingino-android.apk" -o "$THINGINO_DST"
    fi
    ACTUAL_SHA="$(sha256sum "$THINGINO_DST" | awk '{print $1}')"
    if [ "$ACTUAL_SHA" != "$THINGINO_SHA" ]; then
        echo "SHA-256 mismatch for thingino-android.apk: $ACTUAL_SHA != $THINGINO_SHA" >&2
        rm -f "$THINGINO_DST"
        exit 1
    fi
    echo "[+] Verified thingino-android.apk (SHA-256 OK)"
fi

echo ""
echo "[+] Setup complete!"
echo "    Start local portal only:          python3 $ROOT_DIR/server.py"
echo "    Start portal + HTTPS QR tunnel:   python3 $ROOT_DIR/server.py --tunnel"

if [ "$START_MODE" = "plain" ]; then
    exec python3 "$ROOT_DIR/server.py"
elif [ "$START_MODE" = "tunnel" ]; then
    exec python3 "$ROOT_DIR/server.py" --tunnel
fi

# ==============================================================================
# Dockerfile — Self-Hosted Container Image for AREOLE-DPC-HWTF
# ==============================================================================
# Teaching Design Goals:
#   1. Immutable code + zero baked secrets:
#      Signing keys and APKs are NEVER baked into image layers! Instead, your
#      container generates a fresh private keystore inside /var/lib/areole on
#      first boot so every deployment owns its own unique signing identity.
#   2. Complete Android 35 toolchain inside one portable runtime:
#      Includes OpenJDK 21, Python 3, qrencode (SVG QR generator), iproute2
#      (LAN IP discovery), Android SDK 35 + Google platform-tools (adb 37+),
#      and cloudflared (optional zero-account HTTPS tunnel for Android 14-16+).
#   3. Non-root runtime (UID 10001) + clean volume split:
#      /app            -> read-only application code & Android DPC sources
#      /var/lib/areole -> persistent volume holding keystore/, data/, and APKs
# ==============================================================================

FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG TARGETARCH=amd64

# 1. Core OS dependencies:
#    - openjdk-21-jdk-headless: javac & keytool to compile/sign the DPC APK
#    - python3:                 runs server.py (zero external pip dependencies!)
#    - qrencode:                renders sharp SVG QR codes in the Web UI
#    - iproute2:                gives `ip -4 -j addr` for LAN URL detection
#    - curl/unzip/zip/usbutils: fetches SDK & supports optional USB ADB passthrough
RUN apt-get -o Acquire::ForceIPv4=true update -qq && apt-get -o Acquire::ForceIPv4=true install -y --no-install-recommends \
        ca-certificates \
        curl \
        iproute2 \
        openjdk-21-jdk-headless \
        python3 \
        qrencode \
        unzip \
        usbutils \
        zip \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Google's official Android SDK Platform 35, Build-Tools 35.0.0
#    (aapt2/d8/zipalign/apksigner), and modern platform-tools (`adb` 37+).
#    Notice we remove `cmdline-tools` right after sdkmanager finishes so ~160 MB
#    of downloader jars do not bloat the final image.
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV PATH="${ANDROID_HOME}/platform-tools:${PATH}"

RUN mkdir -p "${ANDROID_HOME}/cmdline-tools" \
    && curl -fsSL "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip" -o /tmp/cmdtools.zip \
    && unzip -q /tmp/cmdtools.zip -d "${ANDROID_HOME}/cmdline-tools" \
    && mv "${ANDROID_HOME}/cmdline-tools/cmdline-tools" "${ANDROID_HOME}/cmdline-tools/latest" \
    && rm -f /tmp/cmdtools.zip \
    && yes | "${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager" --sdk_root="${ANDROID_HOME}" \
        "platforms;android-35" \
        "build-tools;35.0.0" \
        "platform-tools" >/dev/null \
    && rm -rf "${ANDROID_HOME}/cmdline-tools" \
    && chmod -R a+rX "${ANDROID_HOME}"

# 3. Install Cloudflare Tunnel CLI (cloudflared) so `--tunnel` / ENABLE_TUNNEL=1
#    can provide a valid HTTPS URL required by Android 14-16+ Setup Wizard.
RUN CF_ARCH=$([ "$TARGETARCH" = "arm64" ] && echo "arm64" || echo "amd64") \
    && curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" -o /usr/local/bin/cloudflared \
    && chmod 0755 /usr/local/bin/cloudflared

# 4. Copy application source & create non-root runtime user + writable state dir
WORKDIR /app
COPY android_dpc/ /app/android_dpc/
COPY static/index.html /app/static/index.html
COPY banner.ans build_dpc.sh server.py docker-entrypoint.sh /app/

RUN chmod +x /app/build_dpc.sh /app/server.py /app/docker-entrypoint.sh \
    && useradd --system --uid 10001 --create-home --home-dir /home/areole areole \
    && mkdir -p /var/lib/areole/keystore /var/lib/areole/data /var/lib/areole/apps /app/android_dpc/build \
    && chown -R areole:areole /var/lib/areole /app/android_dpc/build

# Runtime configuration: keep mutable state outside /app so `/app` can remain clean
ENV AREOLE_MDM_HOST=0.0.0.0 \
    AREOLE_MDM_PORT=8780 \
    AREOLE_KEYSTORE_DIR=/var/lib/areole/keystore \
    AREOLE_DATA_DIR=/var/lib/areole/data \
    AREOLE_APPS_DIR=/var/lib/areole/apps \
    AREOLE_APK_PATH=/var/lib/areole/data/areole-dpc.apk \
    ENABLE_TUNNEL=1 \
    INSTALL_THINGINO=0 \
    REBUILD_APK=0

VOLUME ["/var/lib/areole"]
EXPOSE 8780

USER areole
ENTRYPOINT ["/app/docker-entrypoint.sh"]

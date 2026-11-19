#!/usr/bin/env bash
# ==============================================================================
# build_dpc.sh — Clean-room Android DPC APK Compiler & v2/v3 Signer
#
# Teaching Notes (How an Android APK gets built without Gradle):
#   1. aapt2 compile  -> Compiles XML resources (res/) into binary flat files.
#   2. aapt2 link     -> Merges AndroidManifest.xml + resources -> R.java + APK shell.
#   3. javac          -> Compiles our Java DPC sources + R.java into .class bytecode.
#   4. d8             -> Translates JVM .class files into Dalvik bytecode (classes.dex).
#   5. zip            -> Packs classes.dex into the APK archive.
#   6. zipalign       -> Aligns uncompressed data on 4-byte boundaries (required by Android).
#   7. apksigner      -> Signs with APK Signature Scheme v2 & v3 using your local key.
#                        Android Setup Wizard hashes the public X.509 cert from this key
#                        and checks it against PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM.
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
SDK_DIR="${ANDROID_HOME:-$HOME/.local/share/android-sdk}"
PLATFORM_JAR="$SDK_DIR/platforms/android-35/android.jar"
BT_DIR="$SDK_DIR/build-tools/35.0.0"

if [ ! -f "$PLATFORM_JAR" ] || [ ! -x "$BT_DIR/apksigner" ]; then
    echo "Android SDK 35 not found at $SDK_DIR."
    echo "Run ./setup.sh first to install commandlinetools, android-35, and build-tools 35.0.0."
    exit 1
fi

BUILD_DIR="$ROOT_DIR/android_dpc/build"
SRC_DIR="$ROOT_DIR/android_dpc/src"
RES_DIR="$ROOT_DIR/android_dpc/res"
MANIFEST="$ROOT_DIR/android_dpc/AndroidManifest.xml"
KEYSTORE_DIR="${AREOLE_KEYSTORE_DIR:-$ROOT_DIR/keystore}"
KEYSTORE="$KEYSTORE_DIR/areole-dpc.jks"
PASS_FILE="$KEYSTORE_DIR/.storepass"
APK_OUT="${AREOLE_APK_PATH:-$ROOT_DIR/static/areole-dpc.apk}"

mkdir -p "$BUILD_DIR/obj" "$BUILD_DIR/dex" "$BUILD_DIR/gen" "$KEYSTORE_DIR" "$(dirname "$APK_OUT")"

# Never hardcode passwords in public repositories:
# Generate a local random 24-character keystore password once if not already present.
if [ -n "${AREOLE_KEYSTORE_PASS:-}" ]; then
    KS_PASS="$AREOLE_KEYSTORE_PASS"
elif [ -f "$PASS_FILE" ]; then
    KS_PASS="$(cat "$PASS_FILE")"
else
    KS_PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
    printf '%s' "$KS_PASS" > "$PASS_FILE"
    chmod 600 "$PASS_FILE"
fi

if [ ! -f "$KEYSTORE" ]; then
    echo "[*] Generating local RSA-2048 signing keystore (kept private in keystore/)..."
    keytool -genkeypair -noprompt \
        -keystore "$KEYSTORE" \
        -alias areole-dpc \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -storepass "$KS_PASS" -keypass "$KS_PASS" \
        -dname "CN=AreoleDPC, OU=SelfHosted, O=Community, L=Local, ST=NA, C=US"
fi

rm -rf "$BUILD_DIR/obj" "$BUILD_DIR/dex" "$BUILD_DIR/gen"
mkdir -p "$BUILD_DIR/obj" "$BUILD_DIR/dex" "$BUILD_DIR/gen"

"$BT_DIR/aapt2" compile --dir "$RES_DIR" -o "$BUILD_DIR/res.zip"
"$BT_DIR/aapt2" link \
    -o "$BUILD_DIR/unaligned.apk" \
    --manifest "$MANIFEST" \
    -I "$PLATFORM_JAR" \
    --java "$BUILD_DIR/gen" \
    "$BUILD_DIR/res.zip"

find "$SRC_DIR" "$BUILD_DIR/gen" -name "*.java" > "$BUILD_DIR/sources.txt"
javac --release 11 -classpath "$PLATFORM_JAR" -d "$BUILD_DIR/obj" @"$BUILD_DIR/sources.txt"

"$BT_DIR/d8" --min-api 26 --lib "$PLATFORM_JAR" --output "$BUILD_DIR/dex" $(find "$BUILD_DIR/obj" -name "*.class")

cp "$BUILD_DIR/unaligned.apk" "$BUILD_DIR/with_dex.apk"
(cd "$BUILD_DIR/dex" && zip -q "$BUILD_DIR/with_dex.apk" classes.dex)

"$BT_DIR/zipalign" -f 4 "$BUILD_DIR/with_dex.apk" "$BUILD_DIR/aligned.apk"
"$BT_DIR/apksigner" sign \
    --ks "$KEYSTORE" \
    --ks-key-alias areole-dpc \
    --ks-pass "pass:$KS_PASS" \
    --key-pass "pass:$KS_PASS" \
    --out "$APK_OUT" \
    "$BUILD_DIR/aligned.apk"

"$BT_DIR/apksigner" verify --print-certs "$APK_OUT"
echo "[+] Built & signed: $APK_OUT"

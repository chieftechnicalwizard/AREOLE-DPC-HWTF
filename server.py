#!/usr/bin/env python3
"""
AREOLE-DPC-HWTF — Self-Hosted Android 6-Tap QR Provisioner & Debloat Server
===========================================================================
A single-file, zero-dependency (Python 3 stdlib) provisioning server built to teach
and run clean self-hosted Android Enterprise enrollment without cloud vendor lock-in.

How Android 6-Tap QR Provisioning works under the hood:
  1. On a factory-reset phone's Welcome screen, tapping empty space 6 times starts
     Android's built-in ManagedProvisioning QR reader.
  2. The QR JSON tells ManagedProvisioning where to download areole-dpc.apk
     (PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION), which MUST be served
     over valid HTTPS on Android 14-16+, and must answer HTTP HEAD + GET cleanly.
  3. Android downloads the APK and checks its signing certificate SHA-256 digest
     encoded as URL-safe Base64 without padding (SIGNATURE_CHECKSUM), OR the APK
     file SHA-256 (PACKAGE_CHECKSUM) on older Android 6-9 builds.
  4. Once installed, ManagedProvisioning passes PROVISIONING_ADMIN_EXTRAS_BUNDLE
     into GetProvisioningModeActivity, then PolicyComplianceActivity, then
     AreoleDeviceAdminReceiver.onProfileProvisioningComplete().
  5. Your phone checks into POST /api/device/checkin on this server to report
     its app drawer inventory and receive clean debloat/notification/unenroll tasks.

Security model:
  - When exposed through a temporary Cloudflare Quick Tunnel (--tunnel), ONLY
    phone-facing provisioning routes (/setup, /apk/*.apk, /api/device/checkin)
    are reachable from the public internet.
  - The Web Console (/), QR generator, device command queue, and ADB controls
    return HTTP 403 Forbidden if accessed through a reverse-proxy tunnel header.

Public multi-user mode (--public):
  - Lets strangers share one deployment without seeing or touching each other's
    devices. The browser gets a short-lived server-side session cookie; each
    enrolled phone authenticates with the per-QR enrollment_token it already
    carries (session-scoped, purged at session cleanup; first check-in binds
    token -> device_id).
  - Every admin route is scoped to the session's own devices; ADB control is
    disabled entirely (it drives the server host's own adb daemon).
  - When a session expires, DEPROVISION_KEEP_PERSONAL is auto-queued for each
    of its devices, and all records (devices, inventories, commands, tokens)
    are hard-purged after a grace window.
"""

from __future__ import annotations

import argparse
import atexit
import base64
import glob
import hashlib
import html
import http.server
import ipaddress
import json
import os
import re
import secrets
import shlex
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Portable Paths & Environment Configuration (no hardcoded user directories)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
APPS_DIR = Path(os.environ.get("AREOLE_APPS_DIR", str(STATIC_DIR / "apps")))
DATA_DIR = Path(os.environ.get("AREOLE_DATA_DIR", str(BASE_DIR / "data")))
DB_PATH = DATA_DIR / "areole_mdm.db"
TUNNEL_URL_FILE = DATA_DIR / "tunnel_url.txt"
BANNER_PATH = BASE_DIR / "banner.ans"
APK_PATH = Path(os.environ.get("AREOLE_APK_PATH", str(STATIC_DIR / "areole-dpc.apk")))

ADMIN_COMPONENT = "com.areole.dpc/com.areole.dpc.AreoleDeviceAdminReceiver"

# Public-mode anonymous console session cookie name.
SESSION_COOKIE = "areole_session"

# Optional open-source Thingino IP camera viewer APK pinned to an exact upstream SHA-256.
THINGINO_APK_NAME = "thingino-android.apk"
THINGINO_APK_PATH = APPS_DIR / THINGINO_APK_NAME
THINGINO_APK_URL = "https://github.com/thingino/thingino-app/releases/download/v0.6.0/thingino-android.apk"
THINGINO_APK_SHA256 = "bf4e9181d282f595dd40caf0a8d8b26d16f34135ab96e8acc87f89fde96a81af"

# Curated retail OEM / carrier bloat list (keeps Drive, YT Music, YouTube, Photos, Dialer, Play Store intact).
MOTO_BLOAT_PACKAGES = [
    "com.facebook.katana",
    "com.facebook.system",
    "com.facebook.appmanager",
    "com.facebook.services",
    "com.motorola.demo",
    "com.motorola.genie",
    "com.motorola.help",
    "com.motorola.moto",
    "com.motorola.ccc.notification",
    "com.motorola.brapps",
    "com.motorola.spaces",
    "com.motorola.livewallpaper3",
    "com.motorola.motoedge",
    "com.motorola.gamemode",
    "com.motorola.motocare",
    "com.motorola.paks",
    "com.motorola.android.nativedropboxagent",
    "com.motorola.telemetry",
    "com.motorola.entitlement",
    "com.motorola.motosignature.app",
    "com.motorola.motodisplay",
    "com.aura.oobe.motorola",
    "com.dti.motorola",
    "com.dti.tracfone",
    "com.ironsource.appcloud.oobe",
    "com.LogiaGroup.LogiaDeck",
    "com.motorola.infolife.mobile.services",
    "com.tracfone.generic.mysiteaccount",
    "com.tracfone.generic.mysites",
    "com.tracfone.preload.accountservices",
    "com.swishme.tracfone",
    "com.motorola.tracfone.rsu",
    "com.motorola.tracfone.setup",
    "com.dti.folderlauncher",
    "com.vzw.hss.myverizon",
    "com.verizon.mips.services",
    "com.securityandprivacy.android.verizon.vms",
    "com.aura.jet.att",
    "com.amazon.mShop.android.shopping",
    "com.amazon.appmanager",
    "com.booking",
    "com.linkedin.android",
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
    "com.microsoft.appmanager",
    # Additional OEM/carrier silent installers, trackers & stubs observed on Android 16 (vegas26)
    "com.motorola.installer",
    "com.motorola.smartfeed",
    "com.motorola.motosignature2.app",
    "com.meta.attribution",
    "com.handmark.expressweather",
    "com.inmobi.weather",
    "com.vcast.mediamanager",
    "com.vzw.ecid",
    "com.att.dh",
    "com.att.iqi",
    "com.att.personalcloud",
    "com.att.csoiam.mobilekey",
    "com.cricketwireless.minus",
    "com.cricketwireless.thescoop",
    "com.mizmowireless.acctmgt",
]

CORE_NOTIFICATION_EXEMPT = {
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
    "com.android.vending",
}

_TUNNEL_PROC: subprocess.Popen[str] | None = None

# ---------------------------------------------------------------------------
# Public-mode helpers: per-IP rate limiting & payload sanity checks
# ---------------------------------------------------------------------------
_RATE_BUCKETS: dict[str, dict[str, list[float]]] = {}
_RATE_LOCK = threading.Lock()

# Valid Android package name characters (defensive; also caps list sizes).
_PKG_RE = re.compile(r"^[A-Za-z0-9._]+$")

# Actions a public-mode console may queue (defense-in-depth: the DPC already
# ignores unknown actions, this just stops strangers from queueing arbitrary
# strings against their own devices).
PUBLIC_COMMAND_ACTIONS = {
    "DEPROVISION_KEEP_PERSONAL",
    "STRIP_BLOATWARE",
    "HIDE_PACKAGES",
    "UNHIDE_PACKAGES",
    "CLEAR_RESTRICTIONS",
    "MUTE_NOTIFICATIONS",
    "INSTALL_THINGINO",
}

MAX_INSTALLED_APPS = 1000
MAX_PAYLOAD_PACKAGES = 500
MAX_BODY_BYTES_PUBLIC = 1_000_000


def rate_allow(bucket: str, key: str, limit: int, window: float = 60.0) -> bool:
    """Fixed-window per-key limiter (e.g. 30 check-ins per IP per minute)."""
    now = time.time()
    with _RATE_LOCK:
        bucket_map = _RATE_BUCKETS.setdefault(bucket, {})
        hits = [t for t in bucket_map.get(key, []) if t > now - window]
        if len(hits) >= limit:
            bucket_map[key] = hits
            return False
        hits.append(now)
        bucket_map[key] = hits
        if len(bucket_map) > 4096:  # opportunistic cleanup of idle keys
            for k in list(bucket_map):
                if not [t for t in bucket_map[k] if t > now - window]:
                    del bucket_map[k]
        return True


def validate_command_payload(payload: dict[str, Any] | None) -> str | None:
    """Return an error string for malformed HIDE/UNHIDE payloads, else None."""
    if not payload:
        return None
    pkgs = payload.get("packages")
    if not isinstance(pkgs, list) or not pkgs or len(pkgs) > MAX_PAYLOAD_PACKAGES:
        return f"packages must be a non-empty list of at most {MAX_PAYLOAD_PACKAGES} entries"
    for p in pkgs:
        if not isinstance(p, str) or len(p) > 200 or not _PKG_RE.match(p):
            return f"invalid package name: {p!r}"
    return None


# ---------------------------------------------------------------------------
# SDK & Binary Auto-Discovery
# ---------------------------------------------------------------------------
def _sdk_roots() -> list[Path]:
    """Return candidate Android SDK directories in preference order."""
    roots: list[Path] = []
    for env_key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        val = os.environ.get(env_key, "").strip()
        if val:
            roots.append(Path(val))
    roots.append(Path.home() / ".local" / "share" / "android-sdk")
    roots.append(Path.home() / "Android" / "Sdk")
    return roots


def resolve_apksigner() -> str | None:
    """Find newest apksigner from local Android SDK build-tools or PATH."""
    for root in _sdk_roots():
        candidates = sorted(glob.glob(str(root / "build-tools" / "*" / "apksigner")), reverse=True)
        for cand in candidates:
            if os.access(cand, os.X_OK):
                return cand
    return shutil.which("apksigner")


def resolve_adb() -> str | None:
    """
    Prefer Google's standalone platform-tools adb over OS-packaged adb.
    Reason: Older distro adb builds (e.g. 34.0.4-debian) often fail Wireless ADB
    TLS pairing ('Unable to start pairing client') on Android 13-16 devices.
    """
    for root in _sdk_roots():
        cand = root / "platform-tools" / "adb"
        if os.access(cand, os.X_OK):
            return str(cand)
    return shutil.which("adb")


def resolve_cloudflared() -> str | None:
    """Locate cloudflared in ~/.local/bin or PATH."""
    local_bin = Path.home() / ".local" / "bin" / "cloudflared"
    if os.access(local_bin, os.X_OK):
        return str(local_bin)
    return shutil.which("cloudflared")


# ---------------------------------------------------------------------------
# APK Metadata & Android Signature Checksum Extraction
# ---------------------------------------------------------------------------
_MAX_BODY_BYTES = 1_000_000
_APK_META_LOCK = threading.Lock()
_APK_META_CACHE: tuple[tuple[str, int, int], dict[str, Any]] | None = None
_ADB_TARGET_RE = re.compile(r"^[A-Za-z0-9.\[\]:_-]{1,128}:[0-9]{1,5}$")
_ADB_CODE_RE = re.compile(r"^[0-9]{4,12}$")


def _clean_str(val: Any, default: str = "", max_len: int = 128) -> str:
    if not isinstance(val, str):
        return default
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", val).strip()
    return cleaned[:max_len] if cleaned else default


def _sanitize_adb_username(val: Any) -> str:
    return _clean_str(val, default="Owner", max_len=64)


def _validate_adb_target(val: Any) -> str:
    s = _clean_str(val, default="", max_len=140)
    if not s or s.startswith("-") or not _ADB_TARGET_RE.match(s):
        return ""
    return s


def _validate_adb_code(val: Any) -> str:
    s = _clean_str(val, default="", max_len=16)
    return s if _ADB_CODE_RE.match(s) else ""


def _sanitize_checkin_body(body: dict[str, Any]) -> dict[str, Any]:
    """Validate and bound device check-in fields before persistence."""
    cleaned = dict(body)
    cleaned["device_id"] = _clean_str(body.get("device_id"), default="", max_len=128)
    cleaned["token"] = _clean_str(body.get("token"), default="", max_len=128)
    cleaned["username"] = _clean_str(body.get("username"), default="Owner", max_len=64)
    cleaned["model"] = _clean_str(body.get("model"), default="Android", max_len=128)
    cleaned["android_version"] = _clean_str(body.get("android_version"), default="?", max_len=64)
    cleaned["role"] = _clean_str(body.get("role"), default="UNPROVISIONED", max_len=32)
    try:
        cleaned["hidden_count"] = max(0, min(10_000, int(body.get("hidden_count", 0))))
    except (TypeError, ValueError):
        cleaned["hidden_count"] = 0
    raw_apps = body.get("installed_apps")
    safe_apps: list[dict[str, Any]] = []
    if isinstance(raw_apps, list):
        for item in raw_apps[:1000]:
            if not isinstance(item, dict):
                continue
            pkg = _clean_str(item.get("pkg"), default="", max_len=200)
            if not pkg:
                continue
            safe_apps.append(
                {
                    "pkg": pkg,
                    "label": _clean_str(item.get("label"), default=pkg, max_len=128),
                    "system": bool(item.get("system", False)),
                    "launcher": bool(item.get("launcher", False)),
                    "hidden": bool(item.get("hidden", False)),
                    "bloat_preset": bool(item.get("bloat_preset", False)),
                }
            )
    cleaned["installed_apps"] = safe_apps
    return cleaned


def urlsafe_b64_nopad(raw: bytes) -> str:
    """Android Enterprise QR JSON expects URL-safe Base64 WITHOUT '=' padding."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def compute_apk_metadata() -> dict[str, Any]:
    """
    Compute both checksums Android ManagedProvisioning may ask for:
      - signature_checksum: SHA-256 of the APK signing certificate DER (Android 9+)
      - package_checksum:   SHA-256 of the raw APK file itself (Android 6-9 legacy)
    Cached by (APK_PATH, mtime_ns, size) to avoid spawning apksigner on every request.
    """
    global _APK_META_CACHE
    try:
        st = APK_PATH.stat()
    except OSError:
        return {
            "apk_exists": False,
            "apk_bytes": 0,
            "signature_checksum": "",
            "package_checksum": "",
            "admin_component": ADMIN_COMPONENT,
            "apksigner_path": resolve_apksigner() or "(not found)",
        }

    cache_key = (str(APK_PATH), st.st_mtime_ns, st.st_size)
    with _APK_META_LOCK:
        if _APK_META_CACHE is not None and _APK_META_CACHE[0] == cache_key:
            return dict(_APK_META_CACHE[1])

        apk_bytes = APK_PATH.read_bytes()
        pkg_sha = hashlib.sha256(apk_bytes).digest()

        sig_checksum = ""
        apksigner = resolve_apksigner()
        if apksigner:
            try:
                proc = subprocess.run(
                    [apksigner, "verify", "--print-certs", str(APK_PATH)],
                    capture_output=True,
                    text=True,
                    timeout=12,
                    check=False,
                )
                m = re.search(r"Signer #1 certificate SHA-256 digest:\s*([0-9a-fA-F]{64})", proc.stdout)
                if m:
                    sig_checksum = urlsafe_b64_nopad(bytes.fromhex(m.group(1)))
            except Exception:
                pass

        meta = {
            "apk_exists": True,
            "apk_bytes": len(apk_bytes),
            "signature_checksum": sig_checksum,
            "package_checksum": urlsafe_b64_nopad(pkg_sha),
            "admin_component": ADMIN_COMPONENT,
            "apksigner_path": apksigner or "(not found)",
        }
        _APK_META_CACHE = (cache_key, meta)
        return dict(meta)


_THINGINO_LOCK = threading.Lock()


def ensure_thingino_apk() -> tuple[bool, str]:
    """Download Thingino v0.6.0 APK into static/apps/ safely under lock and verify SHA-256."""
    with _THINGINO_LOCK:
        APPS_DIR.mkdir(parents=True, exist_ok=True)
        if THINGINO_APK_PATH.exists():
            digest = hashlib.sha256(THINGINO_APK_PATH.read_bytes()).hexdigest()
            if digest == THINGINO_APK_SHA256:
                return True, str(THINGINO_APK_PATH)

        tmp_path = APPS_DIR / f".{THINGINO_APK_NAME}.part"
        try:
            req = urllib.request.Request(
                THINGINO_APK_URL,
                headers={"User-Agent": "areole-dpc-hwtf/1.0"},
            )
            with urllib.request.urlopen(req, timeout=90) as resp, open(tmp_path, "wb") as fh:
                shutil.copyfileobj(resp, fh)
            digest = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
            if digest != THINGINO_APK_SHA256:
                tmp_path.unlink(missing_ok=True)
                return False, f"SHA-256 mismatch for Thingino APK ({digest})"
            tmp_path.replace(THINGINO_APK_PATH)
            return True, str(THINGINO_APK_PATH)
        except Exception as exc:
            tmp_path.unlink(missing_ok=True)
            return False, f"Download failed: {exc}"


# ---------------------------------------------------------------------------
# Network Discovery, QR SVG Generation & Cloudflare Quick Tunnel
# ---------------------------------------------------------------------------
def discover_lan_ips() -> list[dict[str, str]]:
    """List non-loopback IPv4 interface addresses via `ip -4 -j addr`."""
    out: list[dict[str, str]] = []
    try:
        res = subprocess.run(["ip", "-4", "-j", "addr"], capture_output=True, text=True, timeout=5)
        for iface in json.loads(res.stdout or "[]"):
            name = iface.get("ifname", "eth")
            if name == "lo":
                continue
            for addr in iface.get("addr_info", []):
                ip = addr.get("local")
                if not ip:
                    continue
                try:
                    if ipaddress.ip_address(ip).is_loopback:
                        continue
                except ValueError:
                    continue
                out.append({"iface": name, "ip": ip})
    except Exception:
        pass
    return out


def get_tunnel_url() -> str:
    """Return active HTTPS provisioning URL (env override or saved tunnel file)."""
    env_url = os.environ.get("AREOLE_TUNNEL_URL", "").strip().rstrip("/")
    if env_url.startswith("https://"):
        return env_url
    if TUNNEL_URL_FILE.exists():
        val = TUNNEL_URL_FILE.read_text(encoding="utf-8").strip().rstrip("/")
        if val.startswith("https://"):
            return val
    return ""


def start_quick_tunnel(port: int) -> str:
    """
    Spawn an ephemeral Cloudflare Quick Tunnel (`trycloudflare.com`) so Android
    14-16 Setup Wizard receives a publicly trusted TLS certificate automatically.
    """
    global _TUNNEL_PROC
    cf = resolve_cloudflared()
    if not cf:
        print("[!] cloudflared not found. Re-run `./setup.sh --with-tunnel` or omit --tunnel for ADB/LAN.", flush=True)
        return ""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TUNNEL_URL_FILE.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [cf, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    _TUNNEL_PROC = proc

    def _cleanup() -> None:
        if _TUNNEL_PROC and _TUNNEL_PROC.poll() is None:
            _TUNNEL_PROC.terminate()

    atexit.register(_cleanup)

    found_event = threading.Event()
    url_holder = [""]

    def _reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            m = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", line)
            if m and not url_holder[0]:
                url_holder[0] = m.group(1)
                TUNNEL_URL_FILE.write_text(url_holder[0] + "\n", encoding="utf-8")
                found_event.set()

    threading.Thread(target=_reader, daemon=True).start()
    if found_event.wait(timeout=20):
        return url_holder[0]
    print("[!] Timed out waiting for trycloudflare.com URL (still continuing HTTP server).", flush=True)
    return ""


def generate_qr_svg(text: str) -> str:
    """Render an inline SVG QR code via `qrencode` (graceful fallback if missing)."""
    qr_bin = shutil.which("qrencode")
    if qr_bin:
        try:
            proc = subprocess.run(
                [qr_bin, "-t", "SVG", "-m", "2", "-o", "-", text],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            if proc.returncode == 0 and "<svg" in proc.stdout:
                idx = proc.stdout.index("<svg")
                return proc.stdout[idx:]
        except Exception:
            pass
    safe = html.escape(text[:80])
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 260 260'>"
        "<rect width='260' height='260' fill='#ffffff'/>"
        "<text x='130' y='120' text-anchor='middle' font-size='13' fill='#0f172a'>Install qrencode for SVG QR</text>"
        f"<text x='130' y='145' text-anchor='middle' font-size='10' fill='#475569'>{safe}...</text>"
        "</svg>"
    )


def build_qr_payload(params: dict[str, Any], apk_meta: dict[str, Any]) -> dict[str, Any]:
    """
    Construct the exact JSON object read by Android's 6-tap Setup Wizard QR scanner.
    Every `android.app.extra.PROVISIONING_*` key is standard AOSP DevicePolicyManager API.
    """
    template_kind = params.get("template", "android9_self")
    host = (params.get("server_url") or get_tunnel_url() or "").strip().rstrip("/")
    if not host:
        ips = discover_lan_ips()
        host = f"http://{ips[0]['ip']}:{params.get('port', 8780)}" if ips else f"http://127.0.0.1:{params.get('port', 8780)}"

    username = (params.get("username") or "Owner").strip() or "Owner"
    pin_hint = (params.get("pin_hint") or "").strip()
    preferred_mode = (params.get("preferred_mode") or "device_owner").strip()
    strip_bloat = bool(params.get("strip_bloatware", True))
    notif_off = bool(params.get("notifications_off", True))
    night_light = bool(params.get("night_light_default", True))
    screen_timeout_5m = bool(params.get("screen_timeout_5m", True))
    install_thingino = bool(params.get("install_thingino", False))
    skip_enc = bool(params.get("skip_encryption", True))
    leave_sys = bool(params.get("leave_system_apps", True))
    wifi_ssid = (params.get("wifi_ssid") or "").strip()
    wifi_pass = (params.get("wifi_password") or "").strip()
    wifi_sec = (params.get("wifi_security") or "WPA").strip()
    # Public mode passes a session-bound token minted (and hash-stored) by MdmDB;
    # self-hosted mode simply generates an opaque one like before.
    token = params.get("enrollment_token") or secrets.token_hex(12)
    auto_retire = bool(params.get("auto_retire", False))

    if template_kind == "manageengine_ref":
        payload: dict[str, Any] = {
            "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION":
                "https://play.google.com/managed/downloadManagingApp?identifier=memdm",
            "android.app.extra.PROVISIONING_SKIP_ENCRYPTION": skip_enc,
            "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE": {
                "DPM": 2,
                "Fqdn": params.get("me_fqdn", "mdm.manageengine.com"),
                "CI": True,
                "Port": "443",
                "Username": username,
                "PinHint": pin_hint,
                "Note": "Reference Managed App Bundle Structure",
            },
            "android.app.extra.PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM":
                "qdbQoq_bFYSbjNMdUf5zuOGxcLqlcML48qP4ZSgpy70=",
            "android.app.extra.PROVISIONING_LEAVE_ALL_SYSTEM_APPS_ENABLED": leave_sys,
            "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME":
                "com.manageengine.mdm.android/com.manageengine.mdm.framework.deviceadmin.DeviceAdminMonitor",
        }
    else:
        payload = {
            "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME": apk_meta["admin_component"],
            "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": f"{host}/apk/areole-dpc.apk",
            "android.app.extra.PROVISIONING_SKIP_ENCRYPTION": skip_enc,
            "android.app.extra.PROVISIONING_LEAVE_ALL_SYSTEM_APPS_ENABLED": leave_sys,
            "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE": {
                "server_url": host,
                "enrollment_token": token,
                "username": username,
                "night_light_default": night_light,
                "screen_timeout_5m": screen_timeout_5m,
                "preferred_mode": preferred_mode,
                "strip_bloatware": strip_bloat,
                "notifications_off_default": notif_off,
                "install_thingino": install_thingino,
                "auto_retire": auto_retire,
            },
        }
        if template_kind == "legacy_6_9":
            payload["android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM"] = apk_meta["package_checksum"]
        else:
            payload["android.app.extra.PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM"] = apk_meta["signature_checksum"]

    if wifi_ssid:
        payload["android.app.extra.PROVISIONING_WIFI_SSID"] = wifi_ssid
        payload["android.app.extra.PROVISIONING_WIFI_SECURITY_TYPE"] = wifi_sec if wifi_pass else "NONE"
        if wifi_pass:
            payload["android.app.extra.PROVISIONING_WIFI_PASSWORD"] = wifi_pass

    return payload


# ---------------------------------------------------------------------------
# Local SQLite Persistence (Devices & Queued Actions)
# ---------------------------------------------------------------------------
class MdmDB:
    def __init__(self, path: Path) -> None:
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    username TEXT,
                    model TEXT,
                    android_version TEXT,
                    role TEXT,
                    hidden_count INTEGER DEFAULT 0,
                    installed_apps_json TEXT DEFAULT '[]',
                    last_seen REAL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT DEFAULT '{}',
                    created_at REAL,
                    delivered INTEGER DEFAULT 0
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    purge_at REAL NOT NULL,
                    retired INTEGER DEFAULT 0
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enrollment_tokens (
                    token_hash TEXT PRIMARY KEY,
                    token_raw TEXT,
                    session_id TEXT NOT NULL,
                    device_id TEXT,
                    created_at REAL NOT NULL
                )
                """
            )
            # Migration for databases created before public mode: add the
            # devices.owner_session and enrollment_tokens.token_raw columns if
            # they are missing.
            device_cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(devices)").fetchall()}
            if "owner_session" not in device_cols:
                self.conn.execute("ALTER TABLE devices ADD COLUMN owner_session TEXT")
            token_cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(enrollment_tokens)").fetchall()}
            if "token_raw" not in token_cols:
                self.conn.execute("ALTER TABLE enrollment_tokens ADD COLUMN token_raw TEXT")

    def upsert_device(self, data: dict[str, Any]) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO devices(device_id, username, model, android_version, role, hidden_count, installed_apps_json, last_seen, owner_session)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    username=excluded.username,
                    model=excluded.model,
                    android_version=excluded.android_version,
                    role=excluded.role,
                    hidden_count=excluded.hidden_count,
                    installed_apps_json=excluded.installed_apps_json,
                    last_seen=excluded.last_seen,
                    owner_session=COALESCE(devices.owner_session, excluded.owner_session)
                """,
                (
                    data.get("device_id", "unknown"),
                    data.get("username", "Owner"),
                    data.get("model", "Android"),
                    data.get("android_version", "?"),
                    data.get("role", "UNPROVISIONED"),
                    int(data.get("hidden_count", 0)),
                    json.dumps(data.get("installed_apps", [])),
                    time.time(),
                    data.get("owner_session"),
                ),
            )

    def list_devices(self, session_id: str | None = None) -> list[dict[str, Any]]:
        """List devices, optionally scoped to one public-mode session's ownership."""
        with self.lock:
            if session_id is not None:
                rows = self.conn.execute(
                    "SELECT * FROM devices WHERE owner_session=? ORDER BY last_seen DESC", (session_id,)
                ).fetchall()
            else:
                rows = self.conn.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["installed_apps"] = json.loads(d.pop("installed_apps_json", "[]") or "[]")
            except Exception:
                d["installed_apps"] = []
            out.append(d)
        return out

    def queue_command(self, device_id: str, action: str, payload: dict[str, Any] | None = None) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO commands(device_id, action, payload_json, created_at, delivered) VALUES (?, ?, ?, ?, 0)",
                (device_id, action, json.dumps(payload or {}), time.time()),
            )

    def pop_commands(self, device_id: str) -> list[dict[str, Any]]:
        with self.lock, self.conn:
            rows = self.conn.execute(
                "SELECT id, action, payload_json FROM commands WHERE device_id=? AND delivered=0 ORDER BY id ASC",
                (device_id,),
            ).fetchall()
            if rows:
                ids = [(r["id"],) for r in rows]
                self.conn.executemany("UPDATE commands SET delivered=1 WHERE id=?", ids)
        out = []
        for r in rows:
            try:
                pl = json.loads(r["payload_json"] or "{}")
            except Exception:
                pl = {}
            out.append({"action": r["action"], "payload": pl})
        return out

    def delete_device(self, device_id: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM devices WHERE device_id=?", (device_id,))
            self.conn.execute("DELETE FROM commands WHERE device_id=?", (device_id,))

    # -----------------------------------------------------------------
    # Public-mode sessions & enrollment tokens
    # -----------------------------------------------------------------
    def create_session(self, ttl_hours: float, grace_hours: float) -> dict[str, Any]:
        """Create a fresh anonymous console session and return its row."""
        sid = secrets.token_hex(16)
        now = time.time()
        expires_at = now + ttl_hours * 3600.0
        purge_at = expires_at + grace_hours * 3600.0
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO sessions(session_id, created_at, expires_at, purge_at, retired) VALUES (?, ?, ?, ?, 0)",
                (sid, now, expires_at, purge_at),
            )
        return {"session_id": sid, "created_at": now, "expires_at": expires_at, "purge_at": purge_at, "retired": 0}

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    def mark_retired(self, session_id: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("UPDATE sessions SET retired=1 WHERE session_id=?", (session_id,))

    def delete_session_cascade(self, session_id: str) -> None:
        """Hard-delete a session plus its tokens, devices, and queued commands."""
        with self.lock, self.conn:
            dev_ids = [
                r["device_id"]
                for r in self.conn.execute("SELECT device_id FROM devices WHERE owner_session=?", (session_id,)).fetchall()
            ]
            if dev_ids:
                marks = ",".join("?" * len(dev_ids))
                self.conn.execute(f"DELETE FROM commands WHERE device_id IN ({marks})", dev_ids)
            self.conn.execute("DELETE FROM devices WHERE owner_session=?", (session_id,))
            self.conn.execute("DELETE FROM enrollment_tokens WHERE session_id=?", (session_id,))
            self.conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))

    def mint_token(self, session_id: str, max_unconsumed: int = 20) -> str | None:
        """
        Mint a new enrollment token for a session. Returns the RAW token, or
        None if the session already holds too many unconsumed tokens. The raw
        value is kept so the console can re-serve the SAME token while the
        visitor edits QR fields (see active_token_raw); it dies with the
        session's purge. Check-in verification still matches by SHA-256 hash.
        """
        raw = secrets.token_hex(12)
        token_hash = hashlib.sha256(raw.encode("ascii")).hexdigest()
        with self.lock, self.conn:
            row = self.conn.execute(
                "SELECT COUNT(*) AS n FROM enrollment_tokens WHERE session_id=? AND device_id IS NULL",
                (session_id,),
            ).fetchone()
            if row and row["n"] >= max_unconsumed:
                return None
            self.conn.execute(
                "INSERT INTO enrollment_tokens(token_hash, token_raw, session_id, device_id, created_at) VALUES (?, ?, ?, NULL, ?)",
                (token_hash, raw, session_id, time.time()),
            )
        return raw

    def active_token_raw(self, session_id: str) -> str | None:
        """Raw value of the session's most recent UNCONSUMED token (re-served as-is)."""
        with self.lock:
            row = self.conn.execute(
                "SELECT token_raw FROM enrollment_tokens WHERE session_id=? AND device_id IS NULL ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        return (row["token_raw"] if row else None) or None

    def revoke_unconsumed_tokens(self, session_id: str) -> None:
        """Invalidate every not-yet-bound token of a session (Regenerate semantics:
        earlier QR printouts that were never scanned stop working immediately)."""
        with self.lock, self.conn:
            self.conn.execute(
                "DELETE FROM enrollment_tokens WHERE session_id=? AND device_id IS NULL",
                (session_id,),
            )

    def checkin_public(self, data: dict[str, Any]) -> tuple[bool, int, str]:
        """
        Atomically authorize a public-mode device check-in under one lock:
          1. Resolve the raw enrollment token by its SHA-256 and reject
             unknown or past-purge tokens.
          2. Reject devices already owned by a different session.
          3. Bind the token to this device first-use-wins (a token can never
             claim a second device) and stamp ownership onto the payload for
             the caller's upsert.
        Returns (ok, http_status, error_message); on ok, data['owner_session']
        has been set.
        """
        raw_token = (data.get("token") or "").strip()
        dev_id = (data.get("device_id") or "").strip()
        if not raw_token or not dev_id:
            return False, 400, "device_id and token required"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        with self.lock, self.conn:
            tok = self.conn.execute(
                """
                SELECT t.token_hash, t.session_id, t.device_id, s.purge_at
                FROM enrollment_tokens t JOIN sessions s ON s.session_id = t.session_id
                WHERE t.token_hash=?
                """,
                (token_hash,),
            ).fetchone()
            if tok is None or tok["purge_at"] <= time.time():
                return False, 401, "Unknown or expired enrollment token"
            owner = self.conn.execute(
                "SELECT owner_session FROM devices WHERE device_id=?", (dev_id,)
            ).fetchone()
            existing = (owner["owner_session"] if owner else None) or None
            if existing is not None and existing != tok["session_id"]:
                return False, 403, "Device already enrolled in another session"
            if tok["device_id"] is None:
                self.conn.execute(
                    "UPDATE enrollment_tokens SET device_id=? WHERE token_hash=?", (dev_id, token_hash)
                )
            elif tok["device_id"] != dev_id:
                return False, 403, "Enrollment token already bound to another device"
            data["owner_session"] = tok["session_id"]
            return True, 200, ""

    def device_owner(self, device_id: str) -> str | None:
        """Return the owning session_id of a device row (None if absent/unowned)."""
        with self.lock:
            row = self.conn.execute(
                "SELECT owner_session FROM devices WHERE device_id=?", (device_id,)
            ).fetchone()
        return (row["owner_session"] if row else None) or None

    def delete_tokens_for_device(self, device_id: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM enrollment_tokens WHERE device_id=?", (device_id,))

    def sessions_to_retire(self, now: float) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM sessions WHERE retired=0 AND expires_at<=?", (now,)
            ).fetchall()
        return [dict(r) for r in rows]

    def sessions_to_purge(self, now: float) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM sessions WHERE purge_at<=?", (now,)).fetchall()
        return [dict(r) for r in rows]

    def owned_device_ids(self, session_id: str) -> list[str]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT device_id FROM devices WHERE owner_session=?", (session_id,)
            ).fetchall()
        return [r["device_id"] for r in rows]


# ---------------------------------------------------------------------------
# USB / Wireless ADB Control Helper (fallback or companion to 6-Tap QR)
# ---------------------------------------------------------------------------
def run_adb(args: list[str], serial: str | None = None, timeout: int = 12) -> tuple[int, str, str]:
    adb = resolve_adb()
    if not adb:
        return 127, "", "adb binary not found (run ./setup.sh to install Google platform-tools)"
    cmd = [adb]
    if serial:
        cmd += ["-s", serial]
    cmd += args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def adb_list_devices() -> list[dict[str, Any]]:
    rc, out, _ = run_adb(["devices", "-l"], timeout=6)
    if rc != 0:
        return []
    devices = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        info: dict[str, Any] = {"serial": serial, "state": state, "model": "?", "android": "?", "users": [], "bloat_present": []}
        if state == "device":
            _, m_out, _ = run_adb(["shell", "getprop", "ro.product.model"], serial)
            _, a_out, _ = run_adb(["shell", "getprop", "ro.build.version.release"], serial)
            _, u_out, _ = run_adb(["shell", "pm", "list", "users"], serial)
            _, p_out, _ = run_adb(["shell", "pm", "list", "packages", "--user", "0", "-e"], serial, timeout=8)
            info["model"] = m_out or "?"
            info["android"] = a_out or "?"
            info["users"] = [u.strip() for u in u_out.splitlines() if "UserInfo{" in u]
            enabled_pkgs = {ln.replace("package:", "").strip() for ln in p_out.splitlines()}
            info["bloat_present"] = [pkg for pkg in MOTO_BLOAT_PACKAGES if pkg in enabled_pkgs]
        devices.append(info)
    return devices


# ---------------------------------------------------------------------------
# HTTP Server & Security Route Gate
# ---------------------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    db: MdmDB
    port: int = 8780
    public_mode: bool = False
    public_base_url: str = ""
    session_ttl: float = 48.0
    retire_grace: float = 24.0

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[areole-dpc] {self.address_string()} - {fmt % args}\n")

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")

    def _check_body_length(self) -> bool:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"error": "Invalid Content-Length"}, 400)
            return False
        if length < 0:
            self._send_json({"error": "Invalid Content-Length"}, 400)
            return False
        if length > _MAX_BODY_BYTES:
            self._send_json({"error": "Request body too large"}, 413)
            return False
        return True

    def _check_admin_csrf(self) -> bool:
        """Require JSON Content-Type and matching Origin (when present) on admin POSTs."""
        ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            self._send_json({"error": "Content-Type must be application/json"}, 415)
            return False
        origin = (self.headers.get("Origin") or "").strip()
        if origin:
            host = (self.headers.get("Host") or "").strip().lower()
            origin_netloc = urllib.parse.urlparse(origin).netloc.lower()
            if not origin_netloc or (host and origin_netloc != host):
                self._send_json({"error": "Cross-origin request rejected"}, 403)
                return False
        return True

    def _is_public_tunnel(self) -> bool:
        """
        Detect whether a request entered via Cloudflare Quick Tunnel rather than
        direct localhost/LAN access. Tunnel visitors cannot touch Admin/ADB UI!
        """
        host = (self.headers.get("Host") or "").lower()
        return bool(
            self.headers.get("CF-Connecting-IP")
            or self.headers.get("CF-Ray")
            or "trycloudflare.com" in host
        )

    # -----------------------------------------------------------------
    # Public-mode session handling (browser cookie + phone enrollment token)
    # -----------------------------------------------------------------
    def _client_ip(self) -> str:
        """
        Best-effort client IP for rate limiting. CF-Connecting-IP is
        authoritative behind Cloudflare; otherwise the RIGHTMOST X-Forwarded-For
        entry is used — earlier entries arrive from the client and are trivially
        spoofable, while the rightmost one was appended by our own trusted
        proxy. Direct connections (no proxy headers) use the socket peer.
        """
        cf = (self.headers.get("CF-Connecting-IP") or "").strip()
        if cf:
            return cf
        xff = (self.headers.get("X-Forwarded-For") or "").strip()
        if xff:
            return xff.split(",")[-1].strip()
        return self.client_address[0] if self.client_address else "unknown"

    def _get_cookie(self, name: str) -> str:
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
        return ""

    def _ensure_session(self) -> dict[str, Any] | None:
        """
        Public mode only: return a live console session for this browser,
        creating one (and queueing a Set-Cookie header) when missing/expired.
        Returns None only when session creation is rate-limited (caller: 429).
        A session is reusable while now < expires_at; between expires_at and
        purge_at it lingers solely so its phones can fetch the queued
        auto-deprovision command, then the sweeper purges everything.
        """
        sid = self._get_cookie(SESSION_COOKIE)
        if sid:
            sess = self.db.get_session(sid)
            if sess and sess["expires_at"] > time.time():
                return sess
        if not rate_allow("session-create", self._client_ip(), 10):
            return None
        sess = self.db.create_session(self.session_ttl, self.retire_grace)
        # Mark Secure only when the request arrived over HTTPS (public
        # deployments terminate TLS at a reverse proxy that sets the header).
        secure = "; Secure" if (self.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip().lower() == "https" else ""
        self._pending_cookie = f"{SESSION_COOKIE}={sess['session_id']}; Path=/; HttpOnly; SameSite=Lax{secure}"
        return sess

    def _emit_pending_cookie(self) -> None:
        cookie = getattr(self, "_pending_cookie", None)
        if cookie:
            self.send_header("Set-Cookie", cookie)
            self._pending_cookie = None

    def _request_public_base_url(self) -> str:
        """Public base URL for QR payloads: configured value, else Host + forwarded proto."""
        if self.public_base_url:
            return self.public_base_url
        host = (self.headers.get("Host") or "").strip() or f"127.0.0.1:{self.port}"
        proto = (self.headers.get("X-Forwarded-Proto") or "http").split(",")[0].strip() or "http"
        return f"{proto}://{host}"

    def _session_owns_device(self, sess: dict[str, Any], device_id: str) -> bool:
        """Ownership check for admin actions; False also when the row is absent."""
        return bool(device_id) and self.db.device_owner(device_id) == sess["session_id"]

    def _send_json(self, obj: Any, status: int = 200) -> None:
        raw = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self._emit_pending_cookie()
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, path: Path, content_type: str, head_only: bool = False) -> None:
        if not path.exists():
            self._send_json({"error": f"File missing: {path.name}"}, 404)
            return
        size = path.stat().st_size
        self.send_response(200)
        self._send_security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self._emit_pending_cookie()
        self.end_headers()
        if not head_only:
            try:
                with open(path, "rb") as fh:
                    shutil.copyfileobj(fh, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                sys.stderr.write(f"[areole-dpc] Client disconnected mid-transfer for {path.name}\n")

    def do_HEAD(self) -> None:
        """Android ManagedProvisioning issues HEAD before GET on the APK download URL."""
        path = self.path.split("?", 1)[0]
        if path == "/apk/areole-dpc.apk":
            self._send_file(APK_PATH, "application/vnd.android.package-archive", head_only=True)
            return
        if path == f"/apk/{THINGINO_APK_NAME}":
            if not THINGINO_APK_PATH.exists():
                ensure_thingino_apk()
            self._send_file(THINGINO_APK_PATH, "application/vnd.android.package-archive", head_only=True)
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]

        # Public phone-facing APK + /setup download page (allowed over tunnel & LAN)
        if path == "/apk/areole-dpc.apk":
            self._send_file(APK_PATH, "application/vnd.android.package-archive")
            return

        if path == f"/apk/{THINGINO_APK_NAME}":
            ok, msg = ensure_thingino_apk()
            if not ok:
                self._send_json({"error": msg}, 502)
                return
            self._send_file(THINGINO_APK_PATH, "application/vnd.android.package-archive")
            return

        if path == "/setup":
            page = """<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>AreoleDPC Setup</title>
<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;max-width:520px;margin:auto}
a.btn{display:block;text-align:center;background:#14b8a6;color:#042f2e;font-weight:700;padding:14px;border-radius:10px;text-decoration:none;margin:14px 0}
a.sec{background:#0284c7;color:#fff}</style></head><body>
<h2>Areole Provisioner DPC</h2>
<p>Install the self-hosted DPC APK directly onto your phone (for post-setup removable BYOD Work Profiles), or scan the web console QR on a factory-reset phone.</p>
<a class='btn' href='/apk/areole-dpc.apk'>Download areole-dpc.apk</a>
<a class='btn sec' href='/apk/thingino-android.apk'>Optional: Thingino Camera Viewer (v0.6.0)</a>
<p style='font-size:13px;color:#94a3b8'>After installing AreoleDPC, open it to manage bloatware or trigger non-destructive deprovisioning anytime.</p>
</body></html>""".encode("utf-8")
            self.send_response(200)
            self._send_security_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return

        # Isolate administrative console & status APIs from public Cloudflare tunnel
        # visitors. Public mode skips this: every admin route is session-gated there,
        # and a real Cloudflare-proxied domain sends CF-* headers that would otherwise
        # lock the operator's own dashboard out.
        if not self.public_mode and self._is_public_tunnel():
            self._send_json({"error": "Admin UI disabled on public tunnel"}, 403)
            return

        if path == "/":
            if self.public_mode and not self._ensure_session():
                self._send_json({"error": "Too many new sessions from this IP"}, 429)
                return
            self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return

        if path == "/api/status":
            apk_meta = compute_apk_metadata()
            if self.public_mode:
                sess = self._ensure_session()
                if not sess:
                    self._send_json({"error": "Too many new sessions from this IP"}, 429)
                    return
                self._send_json(
                    {
                        "port": self.port,
                        "mode": "public",
                        "public_base_url": self._request_public_base_url(),
                        "session": {
                            "created_at": sess["created_at"],
                            "expires_at": sess["expires_at"],
                            "retired": bool(sess["retired"]),
                        },
                        "apk": apk_meta,
                        "thingino_cached": THINGINO_APK_PATH.exists(),
                        "devices": self.db.list_devices(sess["session_id"]),
                    }
                )
                return
            self._send_json(
                {
                    "port": self.port,
                    "mode": "self_hosted",
                    "https_tunnel_url": get_tunnel_url(),
                    "lan_ips": discover_lan_ips(),
                    "apk": apk_meta,
                    "thingino_cached": THINGINO_APK_PATH.exists(),
                    "adb_path": resolve_adb() or "(not found)",
                    "devices": self.db.list_devices(),
                }
            )
            return

        if path == "/api/adb/status":
            if self.public_mode:
                self._send_json({"error": "ADB control disabled in public mode"}, 403)
                return
            self._send_json({"adb_path": resolve_adb(), "devices": adb_list_devices()})
            return

        self._send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        if not self._check_body_length():
            return
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if self.public_mode and length > MAX_BODY_BYTES_PUBLIC:
                self._send_json({"error": "Request body too large"}, 413)
                return
            raw = self.rfile.read(length) if length > 0 else b"{}"
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json({"error": "Invalid JSON body"}, 400)
            return
        if not isinstance(body, dict):
            self._send_json({"error": "JSON object required"}, 400)
            return
        if path == "/api/device/checkin":
            body = _sanitize_checkin_body(body)

        # Allowed over tunnel & LAN so enrolled devices report inventory cleanly
        if path == "/api/device/checkin":
            if self.public_mode:
                if not rate_allow("checkin", self._client_ip(), 30):
                    self._send_json({"error": "Rate limit exceeded"}, 429)
                    return
                ok, status, err = self.db.checkin_public(body)
                if not ok:
                    self._send_json({"error": err}, status)
                    return
                apps = body.get("installed_apps")
                if isinstance(apps, list) and len(apps) > MAX_INSTALLED_APPS:
                    body["installed_apps"] = apps[:MAX_INSTALLED_APPS]
            self.db.upsert_device(body)
            dev_id = body.get("device_id", "")
            cmds = self.db.pop_commands(dev_id) if dev_id else []
            self._send_json({"ok": True, "commands": cmds})
            return

        if not self.public_mode and self._is_public_tunnel():
            self._send_json({"error": "Admin API disabled on public tunnel"}, 403)
            return

        if not self._check_admin_csrf():
            return

        if path == "/api/qr":
            if self.public_mode:
                sess = self._ensure_session()
                if not sess:
                    self._send_json({"error": "Too many new sessions from this IP"}, 429)
                    return
                if not rate_allow("qr", self._client_ip(), 30):
                    self._send_json({"error": "Rate limit exceeded"}, 429)
                    return
                # Re-serve the session's still-unconsumed token so the QR stays
                # stable while the visitor edits fields (the UI re-renders on every
                # keystroke, and minting a fresh token per render would exhaust the
                # pool). A new token is minted only when: none is active, the
                # previous one was consumed by an enrolled device, or the client
                # explicitly asks to rotate (Regenerate button).
                if (body.get("template") or "") != "manageengine_ref":
                    token = None
                    if not body.get("regenerate"):
                        token = self.db.active_token_raw(sess["session_id"])
                    else:
                        # Explicit rotation: earlier unscanned QRs must stop working.
                        self.db.revoke_unconsumed_tokens(sess["session_id"])
                    if token is None:
                        token = self.db.mint_token(sess["session_id"])
                    if token is None:
                        self._send_json({"error": "Too many unconsumed enrollment tokens in this session"}, 429)
                        return
                    body["enrollment_token"] = token
                body["auto_retire"] = True
                # Force the QR to point at this deployment's public origin.
                body["server_url"] = self._request_public_base_url()
            apk_meta = compute_apk_metadata()
            body.setdefault("port", self.port)
            payload = build_qr_payload(body, apk_meta)
            json_text = json.dumps(payload, separators=(",", ":"))
            self._send_json({"payload": payload, "json_text": json_text, "svg": generate_qr_svg(json_text)})
            return

        if path == "/api/device/command":
            dev_id = (body.get("device_id") or "").strip()
            action = (body.get("action") or "").strip()
            if not dev_id or not action:
                self._send_json({"error": "device_id and action required"}, 400)
                return
            if self.public_mode:
                sess = self._ensure_session()
                if not sess:
                    self._send_json({"error": "Too many new sessions from this IP"}, 429)
                    return
                if action not in PUBLIC_COMMAND_ACTIONS:
                    self._send_json({"error": "Unknown action"}, 400)
                    return
                if not self._session_owns_device(sess, dev_id):
                    self._send_json({"error": "Unknown device"}, 404)
                    return
                err = validate_command_payload(body.get("payload"))
                if err:
                    self._send_json({"error": err}, 400)
                    return
            self.db.queue_command(dev_id, action, body.get("payload"))
            self._send_json({"ok": True})
            return

        if path == "/api/device/delete":
            dev_id = (body.get("device_id") or "").strip()
            if self.public_mode and dev_id:
                sess = self._ensure_session()
                if not sess:
                    self._send_json({"error": "Too many new sessions from this IP"}, 429)
                    return
                if not self._session_owns_device(sess, dev_id):
                    self._send_json({"error": "Unknown device"}, 404)
                    return
            if dev_id:
                self.db.delete_device(dev_id)
                if self.public_mode:
                    # Forget the device fully: its enrollment token dies with the row.
                    self.db.delete_tokens_for_device(dev_id)
            self._send_json({"ok": True})
            return

        if path == "/api/adb/action":
            if self.public_mode:
                self._send_json({"error": "ADB control disabled in public mode"}, 403)
                return
            action = body.get("action", "")
            username = _sanitize_adb_username(body.get("username"))
            logs: list[str] = []

            if action == "adb_pair":
                target = _validate_adb_target(body.get("pair_target"))
                code = _validate_adb_code(body.get("pair_code"))
                if not target or not code:
                    self._send_json({"ok": False, "logs": ["Enter a valid IP:PairingPort and numeric pairing code."]}, 400)
                    return
                rc, o, e = run_adb(["pair", target, code], timeout=20)
                logs.append(f"adb pair {target} -> rc={rc} {o} {e}")
                self._send_json({"ok": rc == 0, "logs": logs})
                return

            if action == "adb_connect":
                target = _validate_adb_target(body.get("connect_target"))
                if not target:
                    self._send_json({"ok": False, "logs": ["Enter a valid IP:Port to connect."]}, 400)
                    return
                rc, o, e = run_adb(["connect", target], timeout=15)
                logs.append(f"adb connect {target} -> rc={rc} {o} {e}")
                self._send_json({"ok": rc == 0, "logs": logs})
                return

            devs = adb_list_devices()
            serial = devs[0]["serial"] if devs else None
            if not serial:
                self._send_json({"ok": False, "logs": ["No online ADB device detected."]}, 400)
                return

            if action == "enable_debug_and_name":
                for cmd in (
                    ["shell", "settings", "put", "global", "adb_enabled", "1"],
                    ["shell", "settings", "put", "global", "development_settings_enabled", "1"],
                    ["shell", "settings", "put", "global", "device_name", shlex.quote(username)],
                    ["shell", "settings", "put", "system", "screen_off_timeout", "300000"],
                    ["shell", "settings", "put", "global", "stay_on_while_plugged_in", "7"],
                    ["shell", "settings", "put", "secure", "night_display_activated", "1"],
                ):
                    rc, o, e = run_adb(cmd, serial)
                    logs.append(f"{' '.join(cmd)} -> rc={rc} {o} {e}")
            elif action == "debloat":
                for pkg in MOTO_BLOAT_PACKAGES:
                    rc, o, e = run_adb(["shell", "pm", "uninstall", "-k", "--user", "0", pkg], serial, timeout=8)
                    if rc == 0 or "success" in o.lower():
                        logs.append(f"Uninstalled {pkg} (user 0)")
                    else:
                        rc2, o2, e2 = run_adb(["shell", "pm", "disable-user", "--user", "0", pkg], serial, timeout=8)
                        if rc2 == 0 or "disabled" in (o2 + e2).lower():
                            logs.append(f"Disabled {pkg} (user 0)")
            elif action == "mute_notifications":
                _, plist, _ = run_adb(["shell", "pm", "list", "packages", "-3"], serial, timeout=8)
                muted = 0
                for line in plist.splitlines():
                    pkg = line.replace("package:", "").strip()
                    if not pkg or pkg in CORE_NOTIFICATION_EXEMPT:
                        continue
                    rc_m, _, _ = run_adb(["shell", "appops", "set", pkg, "POST_NOTIFICATION", "ignore"], serial, timeout=6)
                    if rc_m == 0:
                        muted += 1
                logs.append(f"Muted POST_NOTIFICATION for {muted} user-installed packages")
            elif action == "install_dpc":
                if not APK_PATH.exists():
                    logs.append("static/areole-dpc.apk missing — run ./build_dpc.sh first.")
                else:
                    rc, o, e = run_adb(["install", "-r", "-t", str(APK_PATH)], serial, timeout=25)
                    logs.append(f"install -> rc={rc} {o} {e}")
            elif action == "install_thingino":
                ok, msg = ensure_thingino_apk()
                if not ok:
                    logs.append(msg)
                else:
                    rc, o, e = run_adb(["install", "-r", str(THINGINO_APK_PATH)], serial, timeout=45)
                    logs.append(f"install thingino v0.6.0 -> rc={rc} {o} {e}")
            elif action == "create_work_profile":
                if not APK_PATH.exists():
                    logs.append("static/areole-dpc.apk missing — run ./build_dpc.sh first.")
                else:
                    rc, o, e = run_adb(["install", "-r", "-t", str(APK_PATH)], serial, timeout=25)
                    logs.append(f"install -> rc={rc} {o} {e}")
                    rc2, o2, e2 = run_adb(["shell", "pm", "create-user", "--profileOf", "0", "--managed", shlex.quote(username)], serial, timeout=15)
                    logs.append(f"create-user -> rc={rc2} {o2} {e2}")
                    m = re.search(r"id\s+(\d+)", o2)
                    if m:
                        uid = m.group(1)
                        run_adb(["shell", "am", "start-user", uid], serial)
                        rc_u, o_u, e_u = run_adb(["install", "--user", uid, "-r", "-t", str(APK_PATH)], serial, timeout=25)
                        logs.append(f"install --user {uid} -> rc={rc_u} {o_u} {e_u}")
                        rc3, o3, e3 = run_adb(
                            ["shell", "dpm", "set-profile-owner", "--user", uid, "com.areole.dpc/.AreoleDeviceAdminReceiver"],
                            serial,
                        )
                        logs.append(f"set-profile-owner({uid}) -> rc={rc3} {o3} {e3}")
            elif action == "remove_work_profile":
                _, users, _ = run_adb(["shell", "pm", "list", "users"], serial)
                removed = []
                for ln in users.splitlines():
                    if "MANAGED_PROFILE" in ln or username in ln:
                        m = re.search(r"UserInfo\{(\d+):", ln)
                        if m and m.group(1) != "0":
                            uid = m.group(1)
                            rc, o, e = run_adb(["shell", "pm", "remove-user", uid], serial)
                            removed.append(f"remove-user {uid}: rc={rc} {o} {e}")
                logs.extend(removed or ["No secondary managed user found"])
            else:
                logs.append(f"Unknown action: {action}")

            self._send_json({"ok": True, "logs": logs})
            return

        self._send_json({"error": "Not found"}, 404)


def start_expiry_sweeper(db: MdmDB, interval: float = 300.0) -> None:
    """
    Public-mode lifecycle daemon:
      1. Retire: when a session passes expires_at, queue DEPROVISION_KEEP_PERSONAL
         for each of its devices exactly once (delivered whenever the phone next
         checks in — app open, reboot, or its periodic background sync job).
      2. Purge: after the grace window, hard-delete the session, its tokens,
         its devices, inventories, and any undelivered commands.
    """
    def _sweep() -> None:
        while True:
            try:
                now = time.time()
                for sess in db.sessions_to_retire(now):
                    for dev_id in db.owned_device_ids(sess["session_id"]):
                        db.queue_command(dev_id, "DEPROVISION_KEEP_PERSONAL")
                    db.mark_retired(sess["session_id"])
                    sys.stderr.write(
                        f"[areole-dpc] session {sess['session_id'][:8]}… expired: queued auto-deprovision "
                        f"for {len(db.owned_device_ids(sess['session_id']))} device(s)\n"
                    )
                for sess in db.sessions_to_purge(now):
                    db.delete_session_cascade(sess["session_id"])
                    sys.stderr.write(f"[areole-dpc] session {sess['session_id'][:8]}… purged (records deleted)\n")
            except Exception as exc:  # pragma: no cover - sweeper must never die
                sys.stderr.write(f"[areole-dpc] expiry sweeper error: {exc}\n")
            time.sleep(interval)

    threading.Thread(target=_sweep, daemon=True, name="areole-expiry-sweeper").start()


def print_banner() -> None:
    if sys.stdout.isatty() and BANNER_PATH.exists():
        print(BANNER_PATH.read_text(encoding="utf-8", errors="ignore"), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="AREOLE-DPC-HWTF Self-Hosted Android QR Provisioner")
    parser.add_argument("--host", default=os.environ.get("AREOLE_MDM_HOST", "0.0.0.0"), help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("AREOLE_MDM_PORT", "8780")), help="HTTP port (default: 8780)")
    parser.add_argument("--tunnel", action="store_true", help="Start an ephemeral Cloudflare HTTPS tunnel for Android 14-16 6-tap QR")
    parser.add_argument("--no-banner", action="store_true", help="Suppress ANSI art banner on startup")
    parser.add_argument(
        "--public",
        action="store_true",
        default=os.environ.get("AREOLE_PUBLIC", "").strip().lower() in ("1", "true", "yes"),
        help="Run as a public multi-user service: session cookies, token-bound devices, auto-deprovision on expiry, ADB disabled",
    )
    parser.add_argument(
        "--public-base-url",
        default=os.environ.get("AREOLE_PUBLIC_BASE_URL", "").strip().rstrip("/"),
        help="Canonical public origin for QR payloads, e.g. https://areole.example.com (default: derive from Host + X-Forwarded-Proto)",
    )
    parser.add_argument(
        "--session-ttl",
        type=float,
        default=float(os.environ.get("AREOLE_SESSION_TTL", "48")),
        help="Public mode: console session lifetime in hours (default: 48; fractions allowed for testing)",
    )
    parser.add_argument(
        "--retire-grace",
        type=float,
        default=float(os.environ.get("AREOLE_RETIRE_GRACE", "24")),
        help="Public mode: hours after expiry before records are hard-purged (default: 24)",
    )
    args = parser.parse_args()

    if not args.no_banner:
        print_banner()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    APPS_DIR.mkdir(parents=True, exist_ok=True)

    Handler.db = MdmDB(DB_PATH)
    Handler.port = args.port
    Handler.public_mode = args.public
    Handler.public_base_url = args.public_base_url
    Handler.session_ttl = max(args.session_ttl, 0.001)
    Handler.retire_grace = max(args.retire_grace, 0.001)

    srv = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"AreoleDPC Web Console -> http://127.0.0.1:{args.port}", flush=True)

    if args.public:
        if args.tunnel:
            print("[!] --tunnel is not used together with --public (put the site behind your own HTTPS reverse proxy); skipping tunnel.", flush=True)
            args.tunnel = False
        start_expiry_sweeper(Handler.db, interval=float(os.environ.get("AREOLE_SWEEP_INTERVAL", "300")))
        base = Handler.public_base_url or "(derived from request Host header)"
        print(
            f"PUBLIC multi-user mode  -> sessions live {Handler.session_ttl}h, auto-deprovision on expiry, "
            f"records purged after {Handler.retire_grace}h grace, ADB controls disabled. Base URL: {base}",
            flush=True,
        )

    if args.tunnel:
        tunnel_url = start_quick_tunnel(args.port)
        if tunnel_url:
            print(f"HTTPS 6-Tap QR Tunnel  -> {tunnel_url} (Admin UI isolated with 403)", flush=True)

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down cleanly...", flush=True)


if __name__ == "__main__":
    main()

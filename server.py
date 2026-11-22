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
    install_thingino = bool(params.get("install_thingino", False))
    skip_enc = bool(params.get("skip_encryption", True))
    leave_sys = bool(params.get("leave_system_apps", True))
    wifi_ssid = (params.get("wifi_ssid") or "").strip()
    wifi_pass = (params.get("wifi_password") or "").strip()
    wifi_sec = (params.get("wifi_security") or "WPA").strip()
    token = secrets.token_hex(12)

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
                "pin_hint": pin_hint,
                "preferred_mode": preferred_mode,
                "strip_bloatware": strip_bloat,
                "notifications_off_default": notif_off,
                "install_thingino": install_thingino,
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

    def upsert_device(self, data: dict[str, Any]) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO devices(device_id, username, model, android_version, role, hidden_count, installed_apps_json, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    username=excluded.username,
                    model=excluded.model,
                    android_version=excluded.android_version,
                    role=excluded.role,
                    hidden_count=excluded.hidden_count,
                    installed_apps_json=excluded.installed_apps_json,
                    last_seen=excluded.last_seen
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
                ),
            )

    def list_devices(self) -> list[dict[str, Any]]:
        with self.lock:
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

    def _send_json(self, obj: Any, status: int = 200) -> None:
        raw = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
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

        # Isolate administrative console & status APIs from public Cloudflare tunnel visitors
        if self._is_public_tunnel():
            self._send_json({"error": "Admin UI disabled on public tunnel"}, 403)
            return

        if path == "/":
            self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return

        if path == "/api/status":
            apk_meta = compute_apk_metadata()
            self._send_json(
                {
                    "port": self.port,
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
            self._send_json({"adb_path": resolve_adb(), "devices": adb_list_devices()})
            return

        self._send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        if not self._check_body_length():
            return
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length", "0"))
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
            self.db.upsert_device(body)
            dev_id = body.get("device_id", "")
            cmds = self.db.pop_commands(dev_id) if dev_id else []
            self._send_json({"ok": True, "commands": cmds})
            return

        if self._is_public_tunnel():
            self._send_json({"error": "Admin API disabled on public tunnel"}, 403)
            return

        if not self._check_admin_csrf():
            return

        if path == "/api/qr":
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
            self.db.queue_command(dev_id, action, body.get("payload"))
            self._send_json({"ok": True})
            return

        if path == "/api/device/delete":
            dev_id = (body.get("device_id") or "").strip()
            if dev_id:
                self.db.delete_device(dev_id)
            self._send_json({"ok": True})
            return

        if path == "/api/adb/action":
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


def print_banner() -> None:
    if sys.stdout.isatty() and BANNER_PATH.exists():
        print(BANNER_PATH.read_text(encoding="utf-8", errors="ignore"), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="AREOLE-DPC-HWTF Self-Hosted Android QR Provisioner")
    parser.add_argument("--host", default=os.environ.get("AREOLE_MDM_HOST", "0.0.0.0"), help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("AREOLE_MDM_PORT", "8780")), help="HTTP port (default: 8780)")
    parser.add_argument("--tunnel", action="store_true", help="Start an ephemeral Cloudflare HTTPS tunnel for Android 14-16 6-tap QR")
    parser.add_argument("--no-banner", action="store_true", help="Suppress ANSI art banner on startup")
    args = parser.parse_args()

    if not args.no_banner:
        print_banner()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    APPS_DIR.mkdir(parents=True, exist_ok=True)

    Handler.db = MdmDB(DB_PATH)
    Handler.port = args.port

    srv = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"AreoleDPC Web Console -> http://127.0.0.1:{args.port}", flush=True)

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

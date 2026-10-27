"""Offline, device-bound license verification for DCTQ Auto."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
from datetime import date
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Public key only. The matching private key must never be committed to the repository.
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA8pP6vZB1tRjl2HlVhwtm+otkzFVc2nYqZbdfxY+ivso=
-----END PUBLIC KEY-----
"""


def device_id() -> str:
    """Return a stable, non-secret device identifier suitable for offline binding."""
    identity = ""
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            ) as key:
                identity, _ = winreg.QueryValueEx(key, "MachineGuid")
        except (OSError, ImportError):
            identity = ""
    if not identity:
        # Fallback for non-Windows environments and restricted Windows installations.
        identity = f"{platform.system()}|{platform.node()}|{platform.machine()}|{hex(__import__('uuid').getnode())}"
    return hashlib.sha256(identity.strip().encode("utf-8")).hexdigest().upper()


def license_path() -> Path:
    """Store activation outside the application directory, including one-file builds."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "DCTQAuto" / "license.lic"


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def validate_license(document: dict[str, Any], current_device_id: str | None = None) -> tuple[bool, str]:
    """Verify the vendor signature, machine binding, and inclusive expiry date."""
    try:
        payload = document["payload"]
        signature = base64.b64decode(document["signature"], validate=True)
        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
        if not isinstance(public_key, Ed25519PublicKey):
            return False, "Khóa công khai License không hợp lệ."
        public_key.verify(signature, _canonical_payload(payload))
    except (KeyError, TypeError, ValueError, InvalidSignature):
        return False, "License không hợp lệ hoặc chữ ký đã bị thay đổi."
    except Exception:
        return False, "Không thể xác minh License."

    expected_device = current_device_id or device_id()
    if payload.get("device_id") != expected_device:
        return False, "License này được cấp cho một máy tính khác."
    expiry = payload.get("expires_on")
    try:
        expiry_date = date.fromisoformat(expiry)
    except (TypeError, ValueError):
        return False, "Ngày hết hạn trong License không hợp lệ."
    if date.today() > expiry_date:
        return False, f"License đã hết hạn ngày {expiry_date.isoformat()}."
    license_id = payload.get("license_id")
    if not isinstance(license_id, str) or not license_id.strip():
        return False, "License thiếu mã định danh."
    return True, f"License hợp lệ đến hết ngày {expiry_date.strftime('%d/%m/%Y')}."


def read_license(path: Path | None = None) -> tuple[bool, str, dict[str, Any] | None]:
    target = path or license_path()
    if not target.is_file():
        return False, "Chưa kích hoạt License.", None
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError("License must be a JSON object")
    except (OSError, json.JSONDecodeError, ValueError):
        return False, "Không đọc được file License.", None
    valid, message = validate_license(document)
    return valid, message, document

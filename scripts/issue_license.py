#!/usr/bin/env python3
"""Issue an offline DCTQ Auto license. Keep the Ed25519 private key private.

Example:
  python scripts/issue_license.py --device-id DEVICE_ID --expires-on 2026-12-31 --private-key dctq_auto_license_private_key.pem --output customer.lic
"""
from __future__ import annotations

import argparse
import base64
import json
import uuid
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo License offline cho DCTQ Auto")
    parser.add_argument("--device-id", required=True, help="Mã thiết bị hiển thị trong hộp thoại kích hoạt")
    parser.add_argument("--expires-on", required=True, help="Ngày hết hạn YYYY-MM-DD (bao gồm cả ngày này)")
    parser.add_argument("--private-key", required=True, help="Đường dẫn khóa riêng Ed25519 PEM, giữ bí mật")
    parser.add_argument("--output", default="license.lic", help="File License đầu ra")
    parser.add_argument("--customer", default="", help="Tên khách hàng (tùy chọn)")
    args = parser.parse_args()

    try:
        expiry = date.fromisoformat(args.expires_on)
        private_bytes = Path(args.private_key).read_bytes()
        private_key = serialization.load_pem_private_key(private_bytes, password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            raise ValueError("Khóa riêng không phải Ed25519.")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    payload = {
        "license_id": str(uuid.uuid4()).upper(),
        "device_id": args.device_id.strip().upper(),
        "expires_on": expiry.isoformat(),
        "customer": args.customer.strip(),
        "issued_on": date.today().isoformat(),
        "product": "DCTQ Auto",
    }
    signature = private_key.sign(canonical(payload))
    document = {
        "payload": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    output = Path(args.output)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã tạo License: {output.resolve()}")
    print(f"Mã License: {payload['license_id']}")
    print(f"Thiết bị: {payload['device_id']}")
    print(f"Hết hạn: {payload['expires_on']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from datetime import date, timedelta
import base64
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dctq_auto.licensing import PUBLIC_KEY_PEM, validate_license


def _signed_document(payload):
    # Test-only private key is intentionally unrelated to the production public key.
    key = Ed25519PrivateKey.generate()
    signature = key.sign(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    return {"payload": payload, "signature": base64.b64encode(signature).decode()}


def test_invalid_signature_is_rejected():
    payload = {"license_id": "TEST", "device_id": "DEVICE", "expires_on": (date.today() + timedelta(days=2)).isoformat()}
    valid, message = validate_license(_signed_document(payload), current_device_id="DEVICE")
    assert not valid
    assert "không hợp lệ" in message.lower()


def test_expired_license_with_invalid_signature_is_rejected():
    payload = {"license_id": "TEST", "device_id": "DEVICE", "expires_on": (date.today() - timedelta(days=1)).isoformat()}
    valid, _ = validate_license(_signed_document(payload), current_device_id="DEVICE")
    assert not valid

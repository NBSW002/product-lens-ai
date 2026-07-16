import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EncryptedPayload:
    ciphertext: bytes
    nonce: bytes
    auth_tag: bytes
    key_id: str
    algorithm: str = "AES-256-GCM"


class ProductCipher:
    def __init__(self, key: bytes, key_id: str) -> None:
        if len(key) != 32:
            raise ValueError("PRODUCT_ENCRYPTION_KEY must decode to exactly 32 bytes")
        if not key_id:
            raise ValueError("PRODUCT_ENCRYPTION_KEY_ID is required")
        self._key = key
        self.key_id = key_id

    @classmethod
    def from_base64(cls, encoded_key: str, key_id: str) -> "ProductCipher":
        try:
            key = base64.b64decode(encoded_key, validate=True)
        except Exception as exc:
            raise ValueError("PRODUCT_ENCRYPTION_KEY must be valid base64") from exc
        return cls(key=key, key_id=key_id)

    def encrypt_json(self, payload: dict[str, Any]) -> EncryptedPayload:
        aesgcm = self._aesgcm()
        nonce = os.urandom(12)
        plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        encrypted = aesgcm.encrypt(nonce, plaintext, None)
        return EncryptedPayload(
            ciphertext=encrypted[:-16],
            nonce=nonce,
            auth_tag=encrypted[-16:],
            key_id=self.key_id,
        )

    def decrypt_json(self, payload: EncryptedPayload) -> dict[str, Any]:
        aesgcm = self._aesgcm()
        plaintext = aesgcm.decrypt(payload.nonce, payload.ciphertext + payload.auth_tag, None)
        decoded = json.loads(plaintext.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Encrypted product payload must decode to a JSON object")
        return decoded

    def _aesgcm(self):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise RuntimeError("Install cryptography to enable encrypted product storage") from exc
        return AESGCM(self._key)


def decode_base64_secret(value: str, name: str) -> bytes:
    try:
        secret = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError(f"{name} must be valid base64") from exc
    if len(secret) < 32:
        raise ValueError(f"{name} must decode to at least 32 bytes")
    return secret


def hash_lookup(value: str, secret: bytes) -> str:
    normalized = value.strip().lower().encode("utf-8")
    return hmac.new(secret, normalized, hashlib.sha256).hexdigest()

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from config import PBKDF2_ITERATIONS


@dataclass(frozen=True)
class PinDigest:
    salt_b64: str
    hash_b64: str


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_pin(pin: str, pepper: str, *, salt: bytes | None = None) -> PinDigest:
    if salt is None:
        salt = secrets.token_bytes(16)
    material = (pin + "\0" + pepper).encode("utf-8")
    digest = hashlib.pbkdf2_hmac("sha256", material, salt, PBKDF2_ITERATIONS, dklen=32)
    return PinDigest(_b64(salt), _b64(digest))


def verify_pin(pin: str, pepper: str, salt_b64: str, hash_b64: str) -> bool:
    try:
        expected = _unb64(hash_b64)
        salt = _unb64(salt_b64)
    except Exception:
        return False
    material = (pin + "\0" + pepper).encode("utf-8")
    actual = hashlib.pbkdf2_hmac("sha256", material, salt, PBKDF2_ITERATIONS, dklen=32)
    return hmac.compare_digest(actual, expected)


def new_session_secret() -> str:
    return secrets.token_urlsafe(32)


def session_token_hash(token: str, pepper: str) -> str:
    return hmac.new(pepper.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def safe_secret_match(given: str, expected: str) -> bool:
    return hmac.compare_digest(str(given), str(expected))

"""bharatai.infrastructure.security.password_hasher — PBKDF2 password hashing.

Uses the standard library (no third-party dependency). Format:
``pbkdf2_sha256$<iterations>$<b64 salt>$<b64 hash>``. Verification is constant-time.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_SALT_BYTES = 16


def _b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


class Pbkdf2PasswordHasher:
    """Hashes/verifies passwords with PBKDF2-HMAC-SHA256."""

    def __init__(self, iterations: int = 600_000) -> None:
        """Set the PBKDF2 iteration count (higher = slower = stronger)."""
        self._iterations = iterations

    def hash(self, password: str) -> str:
        """Return an encoded salted hash of the password."""
        salt = os.urandom(_SALT_BYTES)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self._iterations)
        return f"{_ALGORITHM}${self._iterations}${_b64encode(salt)}${_b64encode(derived)}"

    def verify(self, password: str, hashed: str) -> bool:
        """Return True if the password matches the encoded hash (constant-time)."""
        parts = hashed.split("$")
        if len(parts) != 4 or parts[0] != _ALGORITHM:
            return False
        _, iterations, salt_b64, expected_b64 = parts
        try:
            salt = _b64decode(salt_b64)
            expected = _b64decode(expected_b64)
            rounds = int(iterations)
        except ValueError:  # bad base64 (binascii.Error subclasses ValueError) or bad int
            return False
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(derived, expected)

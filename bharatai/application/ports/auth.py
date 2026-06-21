"""bharatai.application.ports.auth — security Protocols (ports).

The AuthService depends only on these abstractions; infrastructure provides concrete
implementations (PBKDF2 hashing, JWT tokens, a dev OTP provider). Production swaps the
OTP/token adapters without touching the application layer — no vendor lock-in.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from bharatai.application.dto import TokenClaims
from bharatai.domain.identity import Role


@runtime_checkable
class PasswordHasherPort(Protocol):
    """Hashes and verifies passwords (never stores plaintext)."""

    def hash(self, password: str) -> str: ...
    def verify(self, password: str, hashed: str) -> bool: ...


@runtime_checkable
class TokenServicePort(Protocol):
    """Issues and verifies signed session tokens."""

    def issue(self, user_id: str, role: Role) -> str: ...
    def verify(self, token: str) -> TokenClaims | None: ...


@runtime_checkable
class OtpProviderPort(Protocol):
    """Sends and verifies one-time passcodes (dev: logs; prod: SMS/email gateway)."""

    def request_otp(self, identifier: str) -> None: ...
    def verify_otp(self, identifier: str, code: str) -> bool: ...

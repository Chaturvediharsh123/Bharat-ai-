"""bharatai.infrastructure.security.otp_provider — a development OTP provider.

Generates single-use, time-limited 6-digit codes and "delivers" them by logging (DEV ONLY).
Production swaps an SMS/email gateway adapter behind the same OtpProviderPort. Codes are
compared in constant time and consumed on success.
"""
from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from bharatai.common.logging import get_logger


class DevOtpProvider:
    """In-memory OTP store for local development (NOT for production delivery)."""

    def __init__(
        self,
        ttl_seconds: int = 300,
        app_env: str = "local",
        logger: logging.Logger | None = None,
    ) -> None:
        """Configure the code lifetime, environment, and logger."""
        self._ttl = ttl_seconds
        self._app_env = app_env
        self._logger = logger or get_logger(__name__)
        self._codes: dict[str, tuple[str, datetime]] = {}

    def request_otp(self, identifier: str) -> None:
        """Generate a code for ``identifier`` and 'deliver' it (code logged only on local)."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._codes[identifier] = (code, datetime.now(UTC) + timedelta(seconds=self._ttl))
        if self._app_env == "local":
            # LOCAL DEV ONLY: convenience; the code is a credential, never logged elsewhere.
            self._logger.warning(
                "DEV OTP issued", extra={"identifier": identifier, "otp_code": code}
            )
        else:
            self._logger.warning("OTP issued", extra={"identifier": identifier})

    def verify_otp(self, identifier: str, code: str) -> bool:
        """Return True if the code matches and is unexpired (single-use)."""
        entry = self._codes.get(identifier)
        if entry is None:
            return False
        stored, expiry = entry
        if datetime.now(UTC) > expiry:
            self._codes.pop(identifier, None)
            return False
        if secrets.compare_digest(stored, code):
            self._codes.pop(identifier, None)  # consume on success
            return True
        return False

"""bharatai.infrastructure.security.token_service — JWT session tokens (PyJWT, HS256).

Standards-compliant signed tokens. ``verify`` returns None on any failure (bad signature,
expiry, missing claims, unknown role) so callers treat it as "not authenticated".
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from bharatai.application.dto import TokenClaims
from bharatai.domain.identity import Role

_ALGORITHM = "HS256"


class JwtTokenService:
    """Issues/verifies HS256 JWTs carrying the user id and role."""

    def __init__(self, secret: str, ttl_seconds: int = 3600, issuer: str = "bharatai") -> None:
        """Configure the signing secret, token lifetime, and issuer claim."""
        self._secret = secret
        self._ttl = ttl_seconds
        self._issuer = issuer

    def issue(self, user_id: str, role: Role) -> str:
        """Issue a signed token for a user with an expiry ``ttl_seconds`` from now."""
        now = datetime.now(UTC)
        payload = {
            "sub": user_id,
            "role": role.value,
            "iss": self._issuer,
            "iat": now,
            "exp": now + timedelta(seconds=self._ttl),
        }
        return jwt.encode(payload, self._secret, algorithm=_ALGORITHM)

    def verify(self, token: str) -> TokenClaims | None:
        """Return the verified claims, or None if the token is invalid/expired."""
        try:
            data = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
                issuer=self._issuer,
                options={"require": ["exp", "sub", "role", "iss"]},
            )
        except jwt.PyJWTError:
            return None
        try:
            role = Role(data["role"])
        except ValueError:
            return None
        return TokenClaims(
            user_id=str(data["sub"]),
            role=role,
            expires_at=datetime.fromtimestamp(data["exp"], tz=UTC),
        )

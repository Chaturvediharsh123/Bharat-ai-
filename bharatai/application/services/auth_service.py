"""bharatai.application.services.auth_service — registration, login, OTP, authorization.

Coordinates the user repository, password hasher, token service, and OTP provider. Audit
events are written in their OWN transaction so a FAILED action (which rolls back) is still
recorded — failures are exactly what an audit log must capture.
"""
from __future__ import annotations

from collections.abc import Callable

from bharatai.application.dto import TokenClaims
from bharatai.application.ports.auth import OtpProviderPort, PasswordHasherPort, TokenServicePort
from bharatai.application.ports.repositories import UnitOfWork
from bharatai.common.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DuplicateEntityError,
)
from bharatai.domain.identity import AuditEvent, Permission, Role, User, UserStatus, has_permission

UowFactory = Callable[[], UnitOfWork]


def _normalize_email(email: str) -> str:
    cleaned = email.strip().lower()
    if "@" not in cleaned:
        raise AuthenticationError("a valid email is required")
    return cleaned


class AuthService:
    """Registration, password/OTP login, and permission checks."""

    def __init__(
        self,
        uow_factory: UowFactory,
        hasher: PasswordHasherPort,
        tokens: TokenServicePort,
        otp: OtpProviderPort,
    ) -> None:
        """Inject the UnitOfWork factory and the security ports."""
        self._uow_factory = uow_factory
        self._hasher = hasher
        self._tokens = tokens
        self._otp = otp
        # Verified against on the missing-user path so login latency does not reveal
        # whether an account exists (avoids a timing-based enumeration oracle).
        self._dummy_hash = hasher.hash("timing-equalizer")

    def register(
        self,
        email: str,
        password: str,
        role: Role = Role.CITIZEN,
        full_name: str | None = None,
        phone: str | None = None,
    ) -> User:
        """Create a new active user; raise ConflictError if the email is taken."""
        normalized = _normalize_email(email)
        user = User(
            email=normalized,
            role=role,
            password_hash=self._hasher.hash(password),
            status=UserStatus.ACTIVE,
            full_name=full_name,
            phone=phone,
        )
        try:
            with self._uow_factory() as uow:
                if uow.users.get_by_email(normalized) is not None:
                    raise DuplicateEntityError("email exists")
                uow.users.add(user)
        except DuplicateEntityError:
            self._audit(None, "register", normalized, success=False, detail="email exists")
            raise ConflictError("email is already registered") from None
        self._audit(user.id, "register", normalized, success=True)
        return user

    def authenticate(self, email: str, password: str) -> str:
        """Verify a password and return a session token; raise on failure."""
        normalized = _normalize_email(email)
        with self._uow_factory() as uow:
            user = uow.users.get_by_email(normalized)
        if user is not None and user.status is UserStatus.ACTIVE and user.password_hash is not None:
            ok = self._hasher.verify(password, user.password_hash)
        else:
            self._hasher.verify(password, self._dummy_hash)  # equalize timing; result discarded
            ok = False
        self._audit(user.id if user else None, "login", normalized, success=ok)
        if not ok or user is None:
            raise AuthenticationError("invalid email or password")
        return self._tokens.issue(user.id, user.role)

    def request_otp(self, email: str) -> None:
        """Send a one-time code to the email."""
        self._otp.request_otp(_normalize_email(email))

    def verify_otp(self, email: str, code: str) -> str:
        """Verify an OTP and return a session token (activates a pending account)."""
        normalized = _normalize_email(email)
        with self._uow_factory() as uow:
            user = uow.users.get_by_email(normalized)
            ok = user is not None and self._otp.verify_otp(normalized, code)
            if ok and user is not None and user.status is UserStatus.PENDING:
                user.status = UserStatus.ACTIVE
                uow.users.update(user)
        self._audit(user.id if user else None, "otp_login", normalized, success=ok)
        if not ok or user is None:
            raise AuthenticationError("invalid or expired code")
        return self._tokens.issue(user.id, user.role)

    def principal(self, token: str) -> TokenClaims | None:
        """Return the verified claims for a token, or None if invalid/expired."""
        return self._tokens.verify(token)

    def authorize(self, token: str, permission: Permission) -> TokenClaims:
        """Return the claims if the token's role holds ``permission``; else raise."""
        claims = self._tokens.verify(token)
        if claims is None:
            raise AuthenticationError("missing or invalid token")
        if not has_permission(claims.role, permission):
            raise AuthorizationError(f"role '{claims.role.value}' lacks {permission.value}")
        return claims

    def _audit(
        self,
        actor_id: str | None,
        action: str,
        resource: str | None,
        *,
        success: bool,
        detail: str | None = None,
    ) -> None:
        # Own transaction: persists even when the action it describes failed/rolled back.
        with self._uow_factory() as uow:
            uow.audit_events.add(
                AuditEvent(
                    actor_id=actor_id,
                    action=action,
                    resource=resource,
                    success=success,
                    detail=detail,
                )
            )

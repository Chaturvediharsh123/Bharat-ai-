"""Tests for the AuthService (register, login, OTP, authorization, audit)."""
from __future__ import annotations

import pytest

from bharatai.application.services.audit_service import AuditService
from bharatai.application.services.auth_service import AuthService
from bharatai.common.exceptions import AuthenticationError, AuthorizationError, ConflictError
from bharatai.domain.identity import Permission, Role, UserStatus
from bharatai.infrastructure.db.connection import SqliteConnectionFactory
from bharatai.infrastructure.db.unit_of_work import SqliteUnitOfWork
from bharatai.infrastructure.security.otp_provider import DevOtpProvider
from bharatai.infrastructure.security.password_hasher import Pbkdf2PasswordHasher
from bharatai.infrastructure.security.token_service import JwtTokenService


@pytest.fixture
def auth(factory: SqliteConnectionFactory) -> AuthService:
    def make() -> SqliteUnitOfWork:
        return SqliteUnitOfWork(factory)

    return AuthService(
        make,
        Pbkdf2PasswordHasher(iterations=1000),
        JwtTokenService(secret="test-secret", ttl_seconds=60),
        DevOtpProvider(ttl_seconds=60),
    )


def test_register_then_login(auth: AuthService) -> None:
    user = auth.register("A@B.com", "pw12345", full_name="Asha")
    assert user.email == "a@b.com"  # normalized
    assert user.status is UserStatus.ACTIVE
    token = auth.authenticate("a@b.com", "pw12345")
    claims = auth.principal(token)
    assert claims is not None
    assert claims.user_id == user.id
    assert claims.role is Role.CITIZEN


def test_duplicate_email_conflicts_case_insensitive(auth: AuthService) -> None:
    auth.register("a@b.com", "pw")
    with pytest.raises(ConflictError):
        auth.register("A@B.COM", "pw")


def test_wrong_password_rejected(auth: AuthService) -> None:
    auth.register("a@b.com", "correct")
    with pytest.raises(AuthenticationError):
        auth.authenticate("a@b.com", "incorrect")


def test_authorize_respects_role(auth: AuthService) -> None:
    auth.register("admin@b.com", "pw", role=Role.ADMIN)
    admin_token = auth.authenticate("admin@b.com", "pw")
    assert auth.authorize(admin_token, Permission.MANAGE_USERS).role is Role.ADMIN

    auth.register("c@b.com", "pw")
    citizen_token = auth.authenticate("c@b.com", "pw")
    with pytest.raises(AuthorizationError):
        auth.authorize(citizen_token, Permission.MANAGE_USERS)


def test_invalid_token_is_unauthenticated(auth: AuthService) -> None:
    assert auth.principal("not-a-token") is None
    with pytest.raises(AuthenticationError):
        auth.authorize("not-a-token", Permission.VIEW_SCHEMES)


def test_missing_user_login_rejected_and_audited(
    auth: AuthService, factory: SqliteConnectionFactory
) -> None:
    with pytest.raises(AuthenticationError):
        auth.authenticate("ghost@b.com", "whatever")

    def make() -> SqliteUnitOfWork:
        return SqliteUnitOfWork(factory)

    events = AuditService(make).recent(10)
    assert any(e.action == "login" and not e.success for e in events)


def test_otp_login(auth: AuthService) -> None:
    auth.register("o@b.com", "pw")
    auth.request_otp("o@b.com")
    code = auth._otp._codes["o@b.com"][0]  # noqa: SLF001 - read the dev code
    token = auth.verify_otp("o@b.com", code)
    assert auth.principal(token) is not None


def test_security_actions_are_audited(auth: AuthService, factory: SqliteConnectionFactory) -> None:
    auth.register("a@b.com", "pw")
    auth.authenticate("a@b.com", "pw")
    with pytest.raises(AuthenticationError):
        auth.authenticate("a@b.com", "wrong")

    def make() -> SqliteUnitOfWork:
        return SqliteUnitOfWork(factory)

    events = AuditService(make).recent(10)
    assert "register" in {e.action for e in events}
    assert any(e.action == "login" and e.success for e in events)
    assert any(e.action == "login" and not e.success for e in events)

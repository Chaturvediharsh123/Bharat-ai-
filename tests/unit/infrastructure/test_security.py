"""Tests for the security adapters: PBKDF2 hashing, JWT tokens, dev OTP."""
from __future__ import annotations

import pytest

from bharatai.domain.identity import Role
from bharatai.infrastructure.security.otp_provider import DevOtpProvider
from bharatai.infrastructure.security.password_hasher import Pbkdf2PasswordHasher
from bharatai.infrastructure.security.token_service import JwtTokenService

_FAST = 1000  # low iterations keep tests fast


def test_password_hash_and_verify() -> None:
    hasher = Pbkdf2PasswordHasher(iterations=_FAST)
    hashed = hasher.hash("s3cret!")
    assert "s3cret!" not in hashed
    assert hasher.verify("s3cret!", hashed)
    assert not hasher.verify("wrong", hashed)
    assert not hasher.verify("s3cret!", "not-a-valid-hash")


def test_password_hashes_are_salted() -> None:
    hasher = Pbkdf2PasswordHasher(iterations=_FAST)
    assert hasher.hash("x") != hasher.hash("x")  # unique salt each time


def test_token_issue_and_verify() -> None:
    service = JwtTokenService(secret="k", ttl_seconds=60)
    claims = service.verify(service.issue("user-1", Role.ADMIN))
    assert claims is not None
    assert claims.user_id == "user-1"
    assert claims.role is Role.ADMIN


def test_token_rejects_expired() -> None:
    expired = JwtTokenService(secret="k", ttl_seconds=-10).issue("u", Role.CITIZEN)
    assert JwtTokenService(secret="k").verify(expired) is None


def test_token_rejects_wrong_secret_and_tamper() -> None:
    token = JwtTokenService(secret="k").issue("u", Role.CITIZEN)
    assert JwtTokenService(secret="other").verify(token) is None
    assert JwtTokenService(secret="k").verify(token + "tamper") is None


def test_otp_request_verify_single_use() -> None:
    otp = DevOtpProvider(ttl_seconds=60)
    otp.request_otp("a@b.com")
    code = otp._codes["a@b.com"][0]  # noqa: SLF001 - reading the dev code in a test
    wrong = "000000" if code != "000000" else "111111"
    assert otp.verify_otp("a@b.com", wrong) is False
    assert otp.verify_otp("a@b.com", code) is True
    assert otp.verify_otp("a@b.com", code) is False  # consumed


def test_otp_expired_and_unknown() -> None:
    otp = DevOtpProvider(ttl_seconds=-1)
    otp.request_otp("a@b.com")
    code = otp._codes["a@b.com"][0]  # noqa: SLF001
    assert otp.verify_otp("a@b.com", code) is False  # expired
    assert DevOtpProvider().verify_otp("nobody@x.com", "123456") is False


def test_otp_code_logged_only_on_local(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    with caplog.at_level(logging.WARNING):
        DevOtpProvider(app_env="production").request_otp("a@b.com")
    assert all(not hasattr(record, "otp_code") for record in caplog.records)

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        DevOtpProvider(app_env="local").request_otp("a@b.com")
    assert any(getattr(record, "otp_code", None) for record in caplog.records)

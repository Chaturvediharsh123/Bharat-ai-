"""Tests for settings validation (the default-token-secret guard)."""
from __future__ import annotations

import pytest

from bharatai.config.settings import AppSettings, SecuritySettings


def test_default_secret_rejected_outside_local() -> None:
    with pytest.raises(ValueError, match="TOKEN_SECRET"):
        AppSettings(app_env="production")  # default secret + non-local must fail fast


def test_local_default_secret_allowed() -> None:
    settings = AppSettings(app_env="local")
    assert settings.security.is_default_secret


def test_real_secret_allowed_outside_local() -> None:
    secret = "a-real-32-byte-or-longer-secret!!"
    settings = AppSettings(app_env="production", security=SecuritySettings(token_secret=secret))
    assert not settings.security.is_default_secret

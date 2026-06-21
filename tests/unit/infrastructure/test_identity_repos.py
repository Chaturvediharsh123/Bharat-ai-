"""Round-trip tests for the user and audit repositories (and the 0002 migration)."""
from __future__ import annotations

import pytest

from bharatai.common.exceptions import DuplicateEntityError
from bharatai.domain.identity import AuditEvent, Role, User, UserStatus
from bharatai.infrastructure.db.unit_of_work import SqliteUnitOfWork


def test_user_roundtrip_and_lookup_by_email(uow: SqliteUnitOfWork) -> None:
    user = User(
        email="a@b.com", role=Role.OFFICER, password_hash="ph", status=UserStatus.ACTIVE,
        full_name="Asha", phone="9876543210",
    )
    with uow:
        uow.users.add(user)
    with uow as u:
        loaded = u.users.get(user.id)
        by_email = u.users.get_by_email("a@b.com")
    assert loaded == user
    assert by_email == user


def test_user_email_is_unique(uow: SqliteUnitOfWork) -> None:
    with uow:
        uow.users.add(User(email="dup@b.com"))
        with pytest.raises(DuplicateEntityError):
            uow.users.add(User(email="dup@b.com"))


def test_audit_repo_recent_and_by_actor(uow: SqliteUnitOfWork) -> None:
    with uow:
        uow.audit_events.add(AuditEvent(action="login", actor_id="u1", success=True))
        uow.audit_events.add(AuditEvent(action="register", actor_id="u1", success=False))
    with uow as u:
        recent = u.audit_events.list_recent(10)
        by_actor = u.audit_events.list_by_actor("u1")
    assert len(recent) == 2
    assert {e.action for e in by_actor} == {"login", "register"}

"""bharatai.domain.identity — users, roles, permissions, and audit events.

A small, self-contained Identity context. Like the rest of the domain it depends on
nothing but the standard library and pydantic. Password hashing, tokens, and OTP delivery
are infrastructure concerns kept out of here (the model only holds a ``password_hash`` string).
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import Field

from bharatai.domain.base import Entity


class Role(str, Enum):
    """A user's role, which determines their permissions."""

    CITIZEN = "citizen"
    OFFICER = "officer"
    ADMIN = "admin"


class UserStatus(str, Enum):
    """Account lifecycle state."""

    PENDING = "pending"  # registered but not yet verified
    ACTIVE = "active"
    DISABLED = "disabled"


class Permission(str, Enum):
    """A discrete capability that a role may or may not hold."""

    VIEW_OWN_PROFILE = "view_own_profile"
    EDIT_OWN_PROFILE = "edit_own_profile"
    VIEW_SCHEMES = "view_schemes"
    UPLOAD_DOCUMENT = "upload_document"
    RUN_ELIGIBILITY = "run_eligibility"
    VIEW_ANY_CITIZEN = "view_any_citizen"
    MANAGE_SCHEMES = "manage_schemes"
    VIEW_ANALYTICS = "view_analytics"
    MANAGE_USERS = "manage_users"


_CITIZEN_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.VIEW_OWN_PROFILE,
        Permission.EDIT_OWN_PROFILE,
        Permission.VIEW_SCHEMES,
        Permission.UPLOAD_DOCUMENT,
        Permission.RUN_ELIGIBILITY,
    }
)
_OFFICER_PERMISSIONS: frozenset[Permission] = _CITIZEN_PERMISSIONS | {
    Permission.VIEW_ANY_CITIZEN,
    Permission.MANAGE_SCHEMES,
}
_ADMIN_PERMISSIONS: frozenset[Permission] = _OFFICER_PERMISSIONS | {
    Permission.VIEW_ANALYTICS,
    Permission.MANAGE_USERS,
}

# A role's permissions are a superset of the less-privileged role's (citizen ⊂ officer ⊂ admin).
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.CITIZEN: _CITIZEN_PERMISSIONS,
    Role.OFFICER: _OFFICER_PERMISSIONS,
    Role.ADMIN: _ADMIN_PERMISSIONS,
}


def has_permission(role: Role, permission: Permission) -> bool:
    """Return True if ``role`` is granted ``permission``."""
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


class User(Entity):
    """An authenticated principal. Credentials are stored only as a ``password_hash``."""

    email: str
    role: Role = Role.CITIZEN
    password_hash: str | None = None
    status: UserStatus = UserStatus.PENDING
    full_name: str | None = None
    phone: str | None = None
    citizen_id: str | None = None  # optional link to a CitizenProfile


class AuditEvent(Entity):
    """An append-only record of a security-relevant action (who did what, when)."""

    actor_id: str | None = None
    action: str
    resource: str | None = None
    success: bool = True
    detail: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

"""Tests for the Identity domain: roles, permissions, and the permission lattice."""
from __future__ import annotations

from bharatai.domain.identity import Permission, Role, has_permission


def test_role_permission_lattice() -> None:
    # citizen ⊂ officer ⊂ admin
    assert has_permission(Role.CITIZEN, Permission.VIEW_SCHEMES)
    assert not has_permission(Role.CITIZEN, Permission.MANAGE_SCHEMES)
    assert not has_permission(Role.CITIZEN, Permission.MANAGE_USERS)

    assert has_permission(Role.OFFICER, Permission.MANAGE_SCHEMES)
    assert has_permission(Role.OFFICER, Permission.VIEW_SCHEMES)  # inherits citizen
    assert not has_permission(Role.OFFICER, Permission.MANAGE_USERS)

    assert has_permission(Role.ADMIN, Permission.MANAGE_USERS)
    assert has_permission(Role.ADMIN, Permission.VIEW_ANALYTICS)
    assert has_permission(Role.ADMIN, Permission.MANAGE_SCHEMES)  # inherits officer

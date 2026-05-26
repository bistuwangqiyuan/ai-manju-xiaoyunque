"""V10 §11 — Role-based access control.

Roles (high → low):
    owner   — full control + billing + sso config
    admin   — manage members + api keys + jobs
    editor  — create / edit / publish jobs + assets
    viewer  — read-only

Permissions are simple string tuples; gate a route with::

    require(role, "org:billing:read")
"""
from __future__ import annotations

from typing import Iterable


_ROLE_HIERARCHY = {"owner": 3, "admin": 2, "editor": 1, "viewer": 0}

_PERMISSIONS_BY_ROLE: dict[str, tuple[str, ...]] = {
    "viewer": (
        "job:read", "novel:read", "screenplay:read",
        "asset:read", "usage:read",
    ),
    "editor": (
        "job:read", "job:write", "job:publish",
        "novel:read", "novel:write",
        "screenplay:read", "screenplay:write",
        "asset:read", "asset:write",
        "usage:read",
    ),
    "admin": (
        "job:read", "job:write", "job:publish", "job:delete",
        "novel:read", "novel:write", "novel:delete",
        "screenplay:read", "screenplay:write", "screenplay:delete",
        "asset:read", "asset:write", "asset:delete",
        "member:read", "member:write",
        "apikey:read", "apikey:write",
        "usage:read",
    ),
    "owner": (
        "*",
        "job:read", "job:write", "job:publish", "job:delete",
        "novel:read", "novel:write", "novel:delete",
        "screenplay:read", "screenplay:write", "screenplay:delete",
        "asset:read", "asset:write", "asset:delete",
        "member:read", "member:write", "member:delete",
        "apikey:read", "apikey:write", "apikey:delete",
        "org:read", "org:write",
        "org:billing:read", "org:billing:write",
        "org:sso:read", "org:sso:write",
        "usage:read",
    ),
}


def role_rank(role: str) -> int:
    return _ROLE_HIERARCHY.get(role, -1)


def is_higher_or_equal(role_a: str, role_b: str) -> bool:
    return role_rank(role_a) >= role_rank(role_b)


def permissions_for(role: str) -> set[str]:
    return set(_PERMISSIONS_BY_ROLE.get(role, ()))


def has_permission(role: str, permission: str) -> bool:
    perms = permissions_for(role)
    return "*" in perms or permission in perms


def require(role: str, permission: str) -> None:
    if not has_permission(role, permission):
        raise PermissionError(
            f"role '{role}' lacks required permission '{permission}'"
        )


def filter_permissions(role: str, requested: Iterable[str]) -> list[str]:
    perms = permissions_for(role)
    if "*" in perms:
        return list(requested)
    return [p for p in requested if p in perms]


__all__ = [
    "role_rank", "is_higher_or_equal",
    "permissions_for", "has_permission", "require", "filter_permissions",
]

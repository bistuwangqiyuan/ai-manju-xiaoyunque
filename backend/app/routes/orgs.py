"""V10 §11 — Organization / team management endpoints.

Routes:
    POST   /orgs                              create org (user becomes owner)
    GET    /orgs                              list orgs the user belongs to
    GET    /orgs/{org_id}                     show org details
    POST   /orgs/{org_id}/members             invite member (creates OrgInvite)
    POST   /orgs/invites/{token}/accept       caller accepts an invite
    DELETE /orgs/{org_id}/members/{user_id}   remove member
    POST   /orgs/{org_id}/keys                issue new API key
    GET    /orgs/{org_id}/keys                list API keys
    DELETE /orgs/{org_id}/keys/{key_id}       disable a key
    GET    /orgs/{org_id}/usage               30-day usage rollup
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.enterprise import api_keys as keys_mod
from src.enterprise import invites as invites_mod
from src.enterprise import rbac
from src.enterprise.usage import usage_summary

from ..db import (
    ApiKey, OrgInvite, OrgMember, Organization, User, get_db,
)
from ..security import get_current_user

router = APIRouter(prefix="/orgs", tags=["orgs"])


class OrgCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str | None = None
    plan: str = "team"
    seats_max: int = 10
    monthly_credits_cents: int = 0


class MemberInviteIn(BaseModel):
    email: str
    role: str = "editor"


class ApiKeyCreateIn(BaseModel):
    name: str = "default"
    rate_per_min: int = 60
    monthly_quota_calls: int = 10000
    test: bool = False


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return s or "org"


def _role_in_org(db: Session, user: User, org_id: int) -> str | None:
    row = db.query(OrgMember).filter(
        OrgMember.org_id == org_id, OrgMember.user_id == user.id,
    ).first()
    return row.role if row else None


def _require_role(db: Session, user: User, org_id: int, permission: str) -> str:
    role = _role_in_org(db, user, org_id)
    if role is None:
        raise HTTPException(status_code=404, detail="org not found or no access")
    try:
        rbac.require(role, permission)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return role


# ---------- orgs CRUD ----------

@router.post("")
def create_org(
    body: OrgCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slug = body.slug or _slugify(body.name)
    if db.query(Organization).filter(Organization.slug == slug).first():
        raise HTTPException(status_code=400, detail=f"slug '{slug}' already in use")
    org = Organization(
        name=body.name, slug=slug, owner_user_id=user.id,
        plan=body.plan, seats_max=body.seats_max,
        monthly_credits_cents=body.monthly_credits_cents,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    db.add(OrgMember(org_id=org.id, user_id=user.id, role="owner"))
    db.commit()
    return {
        "id": org.id, "name": org.name, "slug": org.slug,
        "plan": org.plan, "owner_user_id": org.owner_user_id,
        "seats_max": org.seats_max,
    }


@router.get("")
def list_my_orgs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Organization, OrgMember)
        .join(OrgMember, OrgMember.org_id == Organization.id)
        .filter(OrgMember.user_id == user.id)
        .all()
    )
    return {"orgs": [
        {"id": o.id, "name": o.name, "slug": o.slug, "plan": o.plan,
         "role": m.role}
        for (o, m) in rows
    ]}


@router.get("/{org_id}")
def get_org(
    org_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = _require_role(db, user, org_id, "org:read")
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="org not found")
    members = db.query(OrgMember).filter(OrgMember.org_id == org_id).all()
    return {
        "id": org.id, "name": org.name, "slug": org.slug, "plan": org.plan,
        "seats_max": org.seats_max,
        "monthly_credits_cents": org.monthly_credits_cents,
        "monthly_used_cents": org.monthly_used_cents,
        "private_deploy": org.private_deploy,
        "sso_idp_url": org.sso_idp_url,
        "your_role": role,
        "members": [{"user_id": m.user_id, "role": m.role,
                     "joined_at": m.joined_at.isoformat()} for m in members],
    }


# ---------- members + invites ----------

@router.post("/{org_id}/members")
def invite_member(
    org_id: int, body: MemberInviteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_role(db, user, org_id, "member:write")
    if body.role not in ("admin", "editor", "viewer"):
        raise HTTPException(status_code=400, detail="invalid role")
    token = invites_mod.generate_invite_token()
    invite = OrgInvite(
        org_id=org_id, email=body.email, role=body.role,
        token=token, invited_by_user_id=user.id,
        expires_at=invites_mod.default_expiry(7),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return {"invite_id": invite.id, "token": token, "email": body.email,
            "role": body.role, "expires_at": invite.expires_at.isoformat()}


@router.post("/invites/{token}/accept")
def accept_invite(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invite = db.query(OrgInvite).filter(OrgInvite.token == token).first()
    if invite is None:
        raise HTTPException(status_code=404, detail="invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=400, detail="invite already used")
    if invites_mod.is_expired(invite.expires_at):
        raise HTTPException(status_code=400, detail="invite expired")
    # add membership (idempotent)
    existing = db.query(OrgMember).filter(
        OrgMember.org_id == invite.org_id, OrgMember.user_id == user.id,
    ).first()
    if existing is None:
        db.add(OrgMember(org_id=invite.org_id, user_id=user.id,
                         role=invite.role,
                         invited_by_user_id=invite.invited_by_user_id))
    from datetime import datetime as _dt
    invite.accepted_at = _dt.utcnow()
    invite.accepted_by_user_id = user.id
    db.commit()
    return {"org_id": invite.org_id, "role": invite.role, "joined": True}


@router.delete("/{org_id}/members/{user_id}")
def remove_member(
    org_id: int, user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_role(db, user, org_id, "member:delete")
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org and org.owner_user_id == user_id:
        raise HTTPException(status_code=400, detail="cannot remove the org owner")
    row = db.query(OrgMember).filter(
        OrgMember.org_id == org_id, OrgMember.user_id == user_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="member not found")
    db.delete(row)
    db.commit()
    return {"removed_user_id": user_id, "org_id": org_id}


# ---------- API keys ----------

@router.post("/{org_id}/keys")
def issue_key(
    org_id: int, body: ApiKeyCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_role(db, user, org_id, "apikey:write")
    issued = keys_mod.generate(test=body.test)
    row = ApiKey(
        org_id=org_id, issued_by_user_id=user.id, name=body.name,
        prefix=issued.prefix, secret_hash=issued.secret_hash,
        rate_per_min=body.rate_per_min,
        monthly_quota_calls=body.monthly_quota_calls,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id, "prefix": row.prefix, "name": row.name,
        "rate_per_min": row.rate_per_min,
        "monthly_quota_calls": row.monthly_quota_calls,
        "is_test": issued.is_test,
        "raw_token": issued.raw_token,   # returned ONCE
        "warning": "Save this token — it cannot be retrieved later.",
    }


@router.get("/{org_id}/keys")
def list_keys(
    org_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_role(db, user, org_id, "apikey:read")
    rows = db.query(ApiKey).filter(ApiKey.org_id == org_id).all()
    return {"keys": [
        {"id": r.id, "name": r.name, "prefix": r.prefix,
         "rate_per_min": r.rate_per_min, "monthly_quota_calls": r.monthly_quota_calls,
         "monthly_used_calls": r.monthly_used_calls, "enabled": r.enabled,
         "created_at": r.created_at.isoformat() if r.created_at else None,
         "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None}
        for r in rows
    ]}


@router.delete("/{org_id}/keys/{key_id}")
def disable_key(
    org_id: int, key_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_role(db, user, org_id, "apikey:delete")
    row = db.query(ApiKey).filter(
        ApiKey.id == key_id, ApiKey.org_id == org_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="key not found")
    row.enabled = False
    db.commit()
    return {"id": row.id, "enabled": False}


# ---------- usage ----------

@router.get("/{org_id}/usage")
def org_usage(
    org_id: int,
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_role(db, user, org_id, "usage:read")
    from ..db import OrgUsage
    return usage_summary(db, OrgUsage, org_id=org_id, days=days)

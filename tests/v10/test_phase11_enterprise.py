"""Phase 11 — Enterprise / team commercial tests."""
from __future__ import annotations

import pathlib
import time
import pytest


# ---------- §11 RBAC ----------

def test_rbac_hierarchy_and_permissions():
    from src.enterprise import rbac
    assert rbac.role_rank("owner") > rbac.role_rank("admin") > rbac.role_rank("editor") > rbac.role_rank("viewer")
    assert rbac.is_higher_or_equal("admin", "editor") is True
    assert rbac.is_higher_or_equal("viewer", "editor") is False

    # viewer can read but not write
    assert rbac.has_permission("viewer", "job:read")
    assert not rbac.has_permission("viewer", "job:write")
    # editor can write but not manage members
    assert rbac.has_permission("editor", "job:write")
    assert not rbac.has_permission("editor", "member:write")
    # owner has * + everything
    assert rbac.has_permission("owner", "anything-at-all")
    assert rbac.has_permission("owner", "org:billing:read")


def test_rbac_require_raises():
    from src.enterprise import rbac
    with pytest.raises(PermissionError):
        rbac.require("viewer", "job:write")
    rbac.require("admin", "apikey:write")  # no raise


# ---------- §11 API keys ----------

def test_api_key_generate_and_verify():
    from src.enterprise import api_keys
    issued = api_keys.generate(test=False)
    assert issued.raw_token.startswith("xyq_live_")
    assert len(issued.prefix) == 8
    assert api_keys.verify(issued.raw_token, issued.secret_hash) is True
    assert api_keys.verify("bogus_token", issued.secret_hash) is False
    assert api_keys.extract_prefix(issued.raw_token) == issued.prefix


def test_api_key_test_vs_live():
    from src.enterprise import api_keys
    test_k = api_keys.generate(test=True)
    live_k = api_keys.generate(test=False)
    assert api_keys.is_test_key(test_k.raw_token)
    assert not api_keys.is_test_key(live_k.raw_token)


def test_api_key_secret_hash_changes_with_token():
    from src.enterprise import api_keys
    a = api_keys.generate()
    b = api_keys.generate()
    assert a.raw_token != b.raw_token
    assert a.secret_hash != b.secret_hash


# ---------- §11 Rate limiting ----------

def test_rate_limit_allows_under_quota():
    from src.enterprise.rate_limit import TokenBucketLimiter, RateLimitExceeded
    lim = TokenBucketLimiter()
    for _ in range(5):
        lim.check("k1", per_min=60)
    # 5 < 60, no exception
    assert lim.stats("k1")["n_recent"] == 5


def test_rate_limit_blocks_over_quota():
    from src.enterprise.rate_limit import TokenBucketLimiter, RateLimitExceeded
    lim = TokenBucketLimiter()
    for _ in range(3):
        lim.check("k2", per_min=3)
    with pytest.raises(RateLimitExceeded) as exc:
        lim.check("k2", per_min=3)
    assert exc.value.key == "k2"
    assert exc.value.retry_after_seconds >= 0


def test_rate_limit_per_key_isolation():
    from src.enterprise.rate_limit import TokenBucketLimiter
    lim = TokenBucketLimiter()
    for _ in range(2):
        lim.check("a", per_min=2)
    # b should be allowed independently
    lim.check("b", per_min=2)


# ---------- §11 Invites ----------

def test_invite_token_and_expiry():
    from datetime import datetime, timezone, timedelta
    from src.enterprise import invites
    tok = invites.generate_invite_token()
    assert len(tok) >= 32
    fut = invites.default_expiry(7)
    assert fut > datetime.now(timezone.utc)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assert invites.is_expired(past) is True
    assert invites.is_expired(fut) is False


# ---------- §11 ORM integration: orgs + members + keys + usage ----------

@pytest.fixture
def db(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.db import Base

    eng = create_engine(f"sqlite:///{tmp_path / 'tmp.sqlite'}")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    return Session()


def test_orm_org_create_member_and_keys(db):
    from backend.app.db import (
        ApiKey, OrgMember, Organization, User,
    )
    from src.enterprise import api_keys
    u = User(email="owner@x.com", password_hash="h", tier="pro")
    db.add(u)
    db.commit()
    db.refresh(u)
    org = Organization(name="测试团队", slug="team-test",
                       owner_user_id=u.id, plan="team", seats_max=5)
    db.add(org)
    db.commit()
    db.refresh(org)
    db.add(OrgMember(org_id=org.id, user_id=u.id, role="owner"))
    db.commit()

    issued = api_keys.generate(test=False)
    key = ApiKey(
        org_id=org.id, issued_by_user_id=u.id, name="ci",
        prefix=issued.prefix, secret_hash=issued.secret_hash,
        rate_per_min=10, monthly_quota_calls=1000,
    )
    db.add(key)
    db.commit()
    db.refresh(key)

    # lookup_key end-to-end
    found = api_keys.lookup_key(db, ApiKey, issued.raw_token)
    assert found is not None
    assert found.id == key.id
    assert found.org_id == org.id

    # disable + relookup
    key.enabled = False
    db.commit()
    assert api_keys.lookup_key(db, ApiKey, issued.raw_token) is None


def test_orm_usage_increment_and_summary(db):
    from backend.app.db import OrgUsage, Organization, User
    from src.enterprise.usage import increment_usage, usage_summary

    u = User(email="x@y.com", password_hash="h", tier="pro")
    db.add(u)
    db.commit()
    db.refresh(u)
    org = Organization(name="测试2", slug="team2", owner_user_id=u.id,
                       plan="team", seats_max=5)
    db.add(org)
    db.commit()
    db.refresh(org)
    increment_usage(db, OrgUsage, org_id=org.id, jobs_delta=2, episodes_delta=4,
                    minutes_delta=12.5, cost_cents_delta=300, api_calls_delta=20)
    increment_usage(db, OrgUsage, org_id=org.id, jobs_delta=1, episodes_delta=2,
                    minutes_delta=8.0, cost_cents_delta=160, api_calls_delta=15,
                    api_4xx_delta=2)
    summary = usage_summary(db, OrgUsage, org_id=org.id, days=30)
    assert summary["jobs"] == 3
    assert summary["episodes"] == 6
    assert summary["minutes"] == 20.5
    assert summary["cost_cents"] == 460
    assert summary["api_calls"] == 35
    assert summary["api_4xx"] == 2
    assert summary["days"] == 1


def test_orm_org_invite_accept_flow(db):
    from datetime import datetime, timezone, timedelta
    from backend.app.db import (
        OrgInvite, OrgMember, Organization, User,
    )
    from src.enterprise import invites

    owner = User(email="o@a.com", password_hash="h", tier="pro")
    invitee = User(email="i@a.com", password_hash="h", tier="free")
    db.add_all([owner, invitee])
    db.commit()
    db.refresh(owner)
    db.refresh(invitee)
    org = Organization(name="T3", slug="t3", owner_user_id=owner.id,
                       plan="team", seats_max=5)
    db.add(org)
    db.commit()
    db.refresh(org)
    db.add(OrgMember(org_id=org.id, user_id=owner.id, role="owner"))

    inv = OrgInvite(
        org_id=org.id, email=invitee.email, role="editor",
        token=invites.generate_invite_token(),
        invited_by_user_id=owner.id,
        expires_at=invites.default_expiry(7),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)

    assert not invites.is_expired(inv.expires_at)
    # Simulate accept
    db.add(OrgMember(org_id=org.id, user_id=invitee.id, role=inv.role))
    inv.accepted_at = datetime.utcnow()
    inv.accepted_by_user_id = invitee.id
    db.commit()

    members = db.query(OrgMember).filter(OrgMember.org_id == org.id).all()
    assert {m.user_id for m in members} == {owner.id, invitee.id}


# ---------- §11 Public v1 endpoint smoke ----------

def test_public_v1_routes_registered():
    """Importable + carries expected paths."""
    from backend.app.routes import public_v1
    paths = [r.path for r in public_v1.router.routes if hasattr(r, "path")]
    assert "/api/v1/jobs" in paths
    assert "/api/v1/me" in paths
    assert "/api/v1/usage" in paths


# ---------- Helm + alembic artifacts ----------

def test_helm_chart_present():
    chart = pathlib.Path("deploy/enterprise/helm/xyq/Chart.yaml")
    values = pathlib.Path("deploy/enterprise/helm/xyq/values.yaml")
    assert chart.exists()
    assert values.exists()
    text = chart.read_text(encoding="utf-8")
    assert "xiaoyunque" in text
    assert "appVersion" in text


def test_alembic_v10_migration_present():
    p = pathlib.Path("backend/alembic/versions/20260526_0001_v10_enterprise_schema.py")
    assert p.exists()
    txt = p.read_text(encoding="utf-8")
    assert "xyq_organizations" in txt
    assert "xyq_api_keys" in txt

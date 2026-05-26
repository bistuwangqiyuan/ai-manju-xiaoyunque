"""V10 §12 — SSO / OIDC P0 (Phase-0 spec compliance).

Provides minimal helpers needed for enterprise Single Sign-On:

    OIDCProvider     — wraps the basic OIDC handshake (auth URL → code →
                       token → userinfo). Uses urllib so it works
                       without authlib installed.
    parse_id_token   — verifies the JWT ``id_token`` if PyJWT is available,
                       else does best-effort signature-less decode (the
                       caller MUST also have validated via userinfo).
    map_userinfo_to_org_role — convention helpers for routing OIDC claims
                       to org membership.

This is "P0" — enough to integrate with the most common IdPs (Okta,
Azure AD, Google Workspace, Authing, Feishu) for the enterprise
private-deploy product without requiring a JS-based PKCE flow.
"""
from __future__ import annotations

import base64
import json
import logging
import secrets
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class OIDCConfig:
    name: str
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...] = ("openid", "email", "profile")
    auth_endpoint: str = ""
    token_endpoint: str = ""
    userinfo_endpoint: str = ""
    jwks_uri: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = {
            "name": self.name, "issuer": self.issuer,
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scopes": list(self.scopes),
            "auth_endpoint": self.auth_endpoint,
            "token_endpoint": self.token_endpoint,
            "userinfo_endpoint": self.userinfo_endpoint,
            "jwks_uri": self.jwks_uri,
        }
        return d


def discover(cfg: OIDCConfig) -> OIDCConfig:
    """Hit ``${issuer}/.well-known/openid-configuration`` and populate the
    endpoint URLs.  Falls back to the (already-set) values on failure."""
    if cfg.auth_endpoint and cfg.token_endpoint and cfg.userinfo_endpoint:
        return cfg
    url = cfg.issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        cfg.auth_endpoint = data.get("authorization_endpoint", cfg.auth_endpoint)
        cfg.token_endpoint = data.get("token_endpoint", cfg.token_endpoint)
        cfg.userinfo_endpoint = data.get("userinfo_endpoint", cfg.userinfo_endpoint)
        cfg.jwks_uri = data.get("jwks_uri", cfg.jwks_uri)
    except Exception as exc:
        _log.warning("oidc discovery failed for %s: %s", cfg.issuer, exc)
    return cfg


@dataclass
class OIDCAuthRequest:
    auth_url: str
    state: str
    nonce: str


def build_auth_url(cfg: OIDCConfig, *, extra_params: dict[str, str] | None = None
                   ) -> OIDCAuthRequest:
    cfg = discover(cfg)
    if not cfg.auth_endpoint:
        raise RuntimeError("auth_endpoint not configured / discovered")
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "scope": " ".join(cfg.scopes),
        "state": state,
        "nonce": nonce,
    }
    if extra_params:
        params.update(extra_params)
    url = cfg.auth_endpoint + "?" + urllib.parse.urlencode(params)
    return OIDCAuthRequest(auth_url=url, state=state, nonce=nonce)


def exchange_code(cfg: OIDCConfig, code: str) -> dict[str, Any]:
    cfg = discover(cfg)
    if not cfg.token_endpoint:
        raise RuntimeError("token_endpoint not configured / discovered")
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": cfg.redirect_uri,
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
    }).encode()
    req = urllib.request.Request(
        cfg.token_endpoint, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def fetch_userinfo(cfg: OIDCConfig, access_token: str) -> dict[str, Any]:
    cfg = discover(cfg)
    req = urllib.request.Request(
        cfg.userinfo_endpoint, method="GET",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def parse_id_token(id_token: str, *, verify: bool = True,
                   jwks_uri: str | None = None,
                   audience: str | None = None) -> dict[str, Any]:
    """Decode and (optionally) verify an id_token.

    With PyJWT installed and ``verify=True`` we do full signature
    validation against the JWKS at ``jwks_uri``.  Otherwise we return the
    payload claims without verification — caller must rely on userinfo.
    """
    if verify:
        try:
            import jwt  # type: ignore
            from jwt import PyJWKClient  # type: ignore
            if jwks_uri:
                jwk_client = PyJWKClient(jwks_uri)
                key = jwk_client.get_signing_key_from_jwt(id_token).key
                return jwt.decode(id_token, key=key,
                                   algorithms=["RS256", "ES256"],
                                   audience=audience)
        except Exception as exc:
            _log.warning("PyJWT verify failed, falling back to unverified decode: %s", exc)
    # Best-effort base64url decode
    parts = id_token.split(".")
    if len(parts) < 2:
        return {}
    payload_b64 = parts[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return {}


@dataclass
class MappedIdentity:
    email: str
    name: str = ""
    org_slug: str | None = None
    suggested_role: str = "editor"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"email": self.email, "name": self.name,
                "org_slug": self.org_slug,
                "suggested_role": self.suggested_role,
                "raw_claims": self.raw}


_ROLE_CLAIM_MAP = {
    "owner": ["owner", "Owner", "OWNER"],
    "admin": ["admin", "Admin", "Manager"],
    "editor": ["editor", "Editor", "Author"],
    "viewer": ["viewer", "Viewer", "Reader", "ReadOnly"],
}


def map_userinfo_to_org_role(userinfo: dict[str, Any],
                              *, default_role: str = "editor",
                              org_slug: str | None = None,
                              role_claim: str = "role",
                              group_claim: str = "groups",
                              group_to_role: dict[str, str] | None = None,
                              ) -> MappedIdentity:
    """Convert IdP userinfo → MappedIdentity, with role precedence:

        1. explicit ``role_claim`` value, mapped via _ROLE_CLAIM_MAP
        2. any ``group_claim`` membership matching ``group_to_role``
        3. ``default_role``
    """
    role = default_role
    raw_role = str(userinfo.get(role_claim, "")).strip()
    if raw_role:
        for canonical, aliases in _ROLE_CLAIM_MAP.items():
            if raw_role in aliases:
                role = canonical
                break
    if role == default_role and group_to_role:
        for grp in userinfo.get(group_claim, []) or []:
            if grp in group_to_role:
                role = group_to_role[grp]
                break
    email = userinfo.get("email") or userinfo.get("preferred_username") or ""
    name = userinfo.get("name") or userinfo.get("nickname") or email
    return MappedIdentity(
        email=email, name=name, org_slug=org_slug,
        suggested_role=role, raw=dict(userinfo),
    )


__all__ = [
    "OIDCConfig", "OIDCAuthRequest", "MappedIdentity",
    "discover", "build_auth_url", "exchange_code", "fetch_userinfo",
    "parse_id_token", "map_userinfo_to_org_role",
]

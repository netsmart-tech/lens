"""Auth router — /api/auth/login, /callback, /logout, /me.

Phase 1: implements the full OIDC Auth Code + PKCE flow **and** the
`LENS_DEV_AUTH=1` bypass that auto-logs in `LENS_DEV_USER_EMAIL`.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lens.auth.deps import current_user
from lens.auth.oidc import (
    build_authorize_url,
    exchange_code_for_tokens,
    fetch_userinfo,
    generate_pkce,
)
from lens.auth.session import clear_session_cookie, set_session_cookie
from lens.config import settings
from lens.db.session import get_db
from lens.logging import get_logger
from lens.models.core.tenants import Tenant
from lens.models.core.user_tenants import UserTenant
from lens.models.core.users import User
from lens.schemas.auth import AuthMeResponse, TenantWithRoleResponse, UserResponse

log = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _get_or_create_user(
    db: AsyncSession,
    email: str,
    name: str,
    sub: str | None,
    groups: list[str] | None = None,
) -> User:
    """Find-or-create a User row, then reconcile staff status + tenant access from OIDC groups.

    Groups-claim convention (Vince spec):
      - `lens-admin`       → sets `user.is_staff = True` (staff see all tenants)
      - `lens-<tenant-slug>` → upserts a `lens_core.user_tenants` row granting viewer access
    """
    # Prefer linking by authentik_sub; fall back to email.
    user = None
    if sub:
        user = (await db.execute(select(User).where(User.authentik_sub == sub))).scalar_one_or_none()
    if user is None:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(email=email, display_name=name, authentik_sub=sub)
        db.add(user)
        await db.flush()
        await db.refresh(user)
    elif sub and not user.authentik_sub:
        user.authentik_sub = sub
        await db.flush()

    # Reconcile groups on every login — Authentik is the source of truth.
    if groups is not None:
        is_admin = "lens-admin" in groups
        if user.is_staff != is_admin:
            user.is_staff = is_admin
            await db.flush()

        tenant_slugs = {
            g[len("lens-"):]
            for g in groups
            if g.startswith("lens-") and g != "lens-admin"
        }
        if tenant_slugs:
            matched_tenants = (
                await db.execute(select(Tenant).where(Tenant.slug.in_(tenant_slugs)))
            ).scalars().all()
            existing_tenant_ids = {
                ut.tenant_id for ut in (
                    await db.execute(select(UserTenant).where(UserTenant.user_id == user.id))
                ).scalars().all()
            }
            for t in matched_tenants:
                if t.id not in existing_tenant_ids:
                    db.add(UserTenant(user_id=user.id, tenant_id=t.id, role="viewer"))
            await db.flush()

    return user


@router.get("/login")
async def login(db: AsyncSession = Depends(get_db)):
    """Start the OIDC flow — or, in dev bypass mode, log straight in."""
    if settings.lens_dev_auth:
        # Dev bypass: always make the stubbed user staff so the tenant list loads.
        user = await _get_or_create_user(
            db, settings.lens_dev_user_email, settings.lens_dev_user_name,
            sub=None, groups=["lens-admin"],
        )
        resp = RedirectResponse(url=settings.oidc_frontend_url, status_code=302)
        set_session_cookie(resp, str(user.id))
        log.info("dev_auth_login", email=user.email, user_id=str(user.id))
        return resp

    if not settings.oidc_client_id:
        raise HTTPException(status_code=500, detail="OIDC not configured")

    state = secrets.token_urlsafe(32)
    pkce = generate_pkce()
    url = build_authorize_url(state, pkce)

    resp = RedirectResponse(url=url, status_code=302)
    # Short-lived cookies to verify state + carry PKCE verifier to callback.
    resp.set_cookie(
        "oidc_state", state, httponly=True, samesite="lax",
        secure=settings.is_production, max_age=600, path="/",
    )
    resp.set_cookie(
        "oidc_pkce", pkce.verifier, httponly=True, samesite="lax",
        secure=settings.is_production, max_age=600, path="/",
    )
    return resp


@router.get("/callback")
async def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    oidc_state: str | None = Cookie(default=None),
    oidc_pkce: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if error:
        raise HTTPException(status_code=400, detail=f"OIDC error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    if not oidc_state or state != oidc_state:
        raise HTTPException(status_code=400, detail="Invalid OIDC state — possible CSRF")
    if not oidc_pkce:
        raise HTTPException(status_code=400, detail="Missing PKCE verifier cookie")

    tokens = await exchange_code_for_tokens(code, oidc_pkce)
    userinfo = await fetch_userinfo(tokens["access_token"])

    sub = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name") or userinfo.get("preferred_username") or email
    if not email:
        raise HTTPException(status_code=400, detail="No email in OIDC userinfo")

    groups = userinfo.get("groups") or []
    user = await _get_or_create_user(db, email=email, name=name, sub=sub, groups=groups)

    resp = RedirectResponse(url=settings.oidc_frontend_url, status_code=302)
    set_session_cookie(resp, str(user.id))
    resp.delete_cookie("oidc_state", path="/")
    resp.delete_cookie("oidc_pkce", path="/")
    log.info(
        "oidc_login",
        email=user.email,
        user_id=str(user.id),
        is_staff=user.is_staff,
        group_count=len(groups),
    )
    return resp


@router.post("/logout")
async def logout():
    resp = JSONResponse({"status": "ok"})
    clear_session_cookie(resp)
    return resp


@router.get("/me", response_model=AuthMeResponse)
async def me(
    user: User | None = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user + the tenants they can access.

    Frontend `auth-context` expects `{user, tenants[]}` — tenants carry a `role`
    field so the selector can show "owner" vs "viewer" without a second fetch.
    """
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if user.is_staff:
        rows = (
            await db.execute(
                select(Tenant).where(Tenant.archived_at.is_(None)).order_by(Tenant.slug)
            )
        ).scalars().all()
        tenants = [
            TenantWithRoleResponse(
                id=t.id, slug=t.slug, name=t.name,
                color_hex=t.color_hex, logo_ref=t.logo_ref,
                role="owner",
            )
            for t in rows
        ]
    else:
        stmt = (
            select(Tenant, UserTenant.role)
            .join(UserTenant, UserTenant.tenant_id == Tenant.id)
            .where(UserTenant.user_id == user.id, Tenant.archived_at.is_(None))
            .order_by(Tenant.slug)
        )
        rows = (await db.execute(stmt)).all()
        tenants = [
            TenantWithRoleResponse(
                id=t.id, slug=t.slug, name=t.name,
                color_hex=t.color_hex, logo_ref=t.logo_ref,
                role=role,
            )
            for (t, role) in rows
        ]

    return AuthMeResponse(user=UserResponse.model_validate(user), tenants=tenants)

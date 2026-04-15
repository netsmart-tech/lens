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
from lens.models.core.users import User
from lens.schemas.auth import UserResponse

log = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _get_or_create_user(db: AsyncSession, email: str, name: str, sub: str | None) -> User:
    # Prefer linking by authentik_sub; fall back to email.
    if sub:
        result = await db.execute(select(User).where(User.authentik_sub == sub))
        user = result.scalar_one_or_none()
        if user:
            return user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=email, display_name=name, authentik_sub=sub)
        db.add(user)
        await db.flush()
        await db.refresh(user)
    elif sub and not user.authentik_sub:
        user.authentik_sub = sub
        await db.flush()
    return user


@router.get("/login")
async def login(db: AsyncSession = Depends(get_db)):
    """Start the OIDC flow — or, in dev bypass mode, log straight in."""
    if settings.lens_dev_auth:
        user = await _get_or_create_user(
            db, settings.lens_dev_user_email, settings.lens_dev_user_name, sub=None
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

    user = await _get_or_create_user(db, email=email, name=name, sub=sub)

    resp = RedirectResponse(url=settings.oidc_frontend_url, status_code=302)
    set_session_cookie(resp, str(user.id))
    resp.delete_cookie("oidc_state", path="/")
    resp.delete_cookie("oidc_pkce", path="/")
    log.info("oidc_login", email=user.email, user_id=str(user.id))
    return resp


@router.post("/logout")
async def logout():
    resp = JSONResponse({"status": "ok"})
    clear_session_cookie(resp)
    return resp


@router.get("/me", response_model=UserResponse)
async def me(user: User | None = Depends(current_user)):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

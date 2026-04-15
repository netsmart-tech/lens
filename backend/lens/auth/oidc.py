"""Hand-rolled OIDC (Authorization Code + PKCE) against Authentik.

Mirrors the secrets-proxy / billing pattern: the backend owns the OIDC flow,
the frontend receives an HTTP-only session cookie. When `settings.lens_dev_auth`
is True, `/api/auth/login` short-circuits the whole flow and creates (if
needed) + logs in the `LENS_DEV_USER_EMAIL` user.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from lens.config import settings


@dataclass
class PKCE:
    verifier: str
    challenge: str
    method: str = "S256"


def generate_pkce() -> PKCE:
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return PKCE(verifier=verifier, challenge=challenge)


def build_authorize_url(state: str, pkce: PKCE) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": settings.oidc_scopes,
        "state": state,
        "code_challenge": pkce.challenge,
        "code_challenge_method": pkce.method,
    }
    return f"{settings.oidc_authorize_url}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, pkce_verifier: str) -> dict:
    """Exchange an authorization code for tokens at Authentik's token endpoint."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            settings.oidc_token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.oidc_redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
                "code_verifier": pkce_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_userinfo(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            settings.oidc_userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()

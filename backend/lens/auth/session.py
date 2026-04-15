"""Signed session cookies via itsdangerous.

Stores only `{"user_id": "<uuid>"}`. Cookies are signed (not encrypted) — the
user-id is not a secret on its own; the signature prevents tampering.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from lens.config import settings


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="lens-session-v1")


def encode_session(data: dict[str, Any]) -> str:
    return _serializer().dumps(json.dumps(data, sort_keys=True))


def decode_session(token: str) -> dict[str, Any] | None:
    try:
        raw = _serializer().loads(token, max_age=settings.session_max_age_hours * 3600)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set_session_cookie(response: Response, user_id: str) -> None:
    token = encode_session({"user_id": user_id})
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.session_max_age_hours * 3600,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")

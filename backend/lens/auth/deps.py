"""Current-user dependencies."""

from __future__ import annotations

import uuid

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lens.auth.session import decode_session
from lens.config import settings
from lens.db.session import get_db
from lens.models.core.users import User


async def current_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Return the logged-in user, or None if no valid session."""
    if not session_token:
        return None
    payload = decode_session(session_token)
    if not payload or "user_id" not in payload:
        return None
    try:
        user_id = uuid.UUID(payload["user_id"])
    except (ValueError, TypeError):
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def require_authenticated(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def require_staff(user: User = Depends(require_authenticated)) -> User:
    if not user.is_staff:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff only")
    return user

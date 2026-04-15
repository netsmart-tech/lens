"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from lens.config import settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}

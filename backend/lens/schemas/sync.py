"""Pydantic shape for the `sync` envelope block.

See DESIGN §3.7 — every list endpoint wraps its items with this.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

SyncStateLiteral = Literal[
    "never-synced",
    "syncing-first-pass",
    "synced-but-empty",
    "stale",
    "failed",
    "fresh",
]


class SyncProgress(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pct: int


class SyncBlock(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: SyncStateLiteral
    last_run_at: datetime | None = None
    last_cursor_at: datetime | None = None
    last_error: str | None = None
    progress: SyncProgress | None = None

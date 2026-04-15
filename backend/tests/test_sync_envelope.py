"""Unit tests for the 5-state sync envelope computation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from lens.services.sync_envelope import _compute_state


def _state(**kwargs) -> SimpleNamespace:
    defaults = dict(
        mode="incremental",
        last_run_at=None,
        last_success_at=None,
        last_error=None,
        backfill_complete_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_never_synced_when_no_sync_state_row() -> None:
    assert _compute_state(None, [], datetime.now(UTC)) == "never-synced"


def test_syncing_first_pass_when_backfill_active() -> None:
    ss = _state(mode="backfill", backfill_complete_at=None, last_run_at=datetime.now(UTC))
    assert _compute_state(ss, [], datetime.now(UTC)) == "syncing-first-pass"


def test_failed_when_last_error_set() -> None:
    ss = _state(last_error="boom", last_run_at=datetime.now(UTC))
    assert _compute_state(ss, [], datetime.now(UTC)) == "failed"


def test_stale_when_last_run_is_old() -> None:
    now = datetime.now(UTC)
    ss = _state(last_run_at=now - timedelta(hours=2))
    assert _compute_state(ss, [1, 2, 3], now) == "stale"


def test_synced_but_empty_when_items_zero() -> None:
    ss = _state(last_run_at=datetime.now(UTC))
    assert _compute_state(ss, [], datetime.now(UTC)) == "synced-but-empty"


def test_fresh_is_default() -> None:
    ss = _state(last_run_at=datetime.now(UTC))
    assert _compute_state(ss, [1, 2], datetime.now(UTC)) == "fresh"

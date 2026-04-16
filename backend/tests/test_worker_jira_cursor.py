"""`_format_jql_datetime` must emit JQL-safe `"yyyy-MM-dd HH:mm"` (UTC)."""

from __future__ import annotations

from lens.workers.jira import _format_jql_datetime


def test_format_strips_fractional_seconds_and_offset() -> None:
    # The cursor form Postgres round-trips (what broke prod).
    assert _format_jql_datetime("2026-04-15T15:05:06.938000-04:00") == "2026-04-15 19:05"


def test_format_accepts_z_suffix() -> None:
    assert _format_jql_datetime("2026-04-15T19:05:06.938000Z") == "2026-04-15 19:05"


def test_format_assumes_utc_when_naive() -> None:
    assert _format_jql_datetime("2026-04-15T19:05:06") == "2026-04-15 19:05"


def test_format_rounds_down_seconds() -> None:
    # 15:05:59 -> 15:05 (minute precision truncates, doesn't round).
    assert _format_jql_datetime("2026-04-15T15:05:59+00:00") == "2026-04-15 15:05"

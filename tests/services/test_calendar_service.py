"""Tests for Calendar service layer: staging, source identity, job submission."""
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import psycopg
import pytest
from conftest import TEST_DSN, make_test_config

from cos.config import GoogleCalendarConnectorConfig
from cos.connectors.calendar import CalendarEvent
from cos.services.calendar import (
    CalendarSyncDegradedError,
    CalendarSyncResult,
    sync_calendar,
)


def _make_event(
    event_id: str = "event-001",
    calendar_id: str = "primary",
    summary: str = "Board Sync",
    start: str = "2026-05-10T09:00:00Z",
    end: str = "2026-05-10T10:00:00Z",
    is_all_day: bool = False,
    attendees: list[str] | None = None,
    organizer: str = "Alice <alice@example.com>",
    description: str = "Quarterly board sync",
    html_link: str = "https://calendar.google.com/event?id=event-001",
    recurring_event_id: str | None = None,
    original_start_time: str | None = None,
) -> CalendarEvent:
    return CalendarEvent(
        event_id=event_id,
        calendar_id=calendar_id,
        summary=summary,
        start=start,
        end=end,
        is_all_day=is_all_day,
        attendees=attendees or ["Bob <bob@example.com>"],
        organizer=organizer,
        description=description,
        html_link=html_link,
        status="confirmed",
        recurring_event_id=recurring_event_id,
        original_start_time=original_start_time,
    )


def _patch_calendar(events: list[CalendarEvent]):
    """Patch Calendar API calls to return synthetic events."""
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        service = MagicMock()
        with (
            patch("cos.services.calendar.build_calendar_service", return_value=service),
            patch("cos.services.calendar.list_events", return_value=[MagicMock()]),
            patch("cos.services.calendar.normalise_event", side_effect=events),
        ):
            yield

    return _ctx()


# ── basic sync ────────────────────────────────────────────────────────────────

async def test_sync_calendar_enqueues_job(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["google_calendar"],
            "google_calendar": GoogleCalendarConnectorConfig(
                staging_dir=tmp_path / "staging"
            ),
        }
    )

    event = _make_event(event_id="ev-001", summary="Q3 Review")
    with _patch_calendar([event]):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await sync_calendar(config, conn)

    assert result.calendars_scanned == 1
    assert result.events_discovered == 1
    assert result.jobs_enqueued == 1

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        row = await (await conn.execute("SELECT payload FROM jobs")).fetchone()

    assert row is not None
    payload = row[0]
    assert payload["source_type"] == "google_calendar_event"
    assert "google-calendar://calendar/primary/event/ev-001" == payload["source_locator"]
    assert payload["metadata"]["connector"] == "google_calendar"
    assert payload["metadata"]["calendar_id"] == "primary"
    assert payload["metadata"]["event_id"] == "ev-001"


async def test_sync_calendar_stages_markdown_file(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["google_calendar"],
            "google_calendar": GoogleCalendarConnectorConfig(staging_dir=staging_dir),
        }
    )

    event = _make_event(
        event_id="ev-002",
        summary="Leadership Review",
        description="Important review",
        attendees=["Charlie <charlie@example.com>"],
        organizer="Alice <alice@example.com>",
        start="2026-05-10T09:00:00Z",
        end="2026-05-10T10:00:00Z",
    )
    with _patch_calendar([event]):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await sync_calendar(config, conn)

    staged_files = list(staging_dir.glob("*.md"))
    assert len(staged_files) == 1

    content = staged_files[0].read_text(encoding="utf-8")
    assert "Leadership Review" in content
    assert "Charlie <charlie@example.com>" in content
    assert "Alice <alice@example.com>" in content
    assert "Important review" in content
    assert "2026-05-10T09:00:00Z" in content


async def test_sync_calendar_source_alias_is_deterministic(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["google_calendar"],
            "google_calendar": GoogleCalendarConnectorConfig(
                staging_dir=tmp_path / "staging"
            ),
        }
    )

    event = _make_event(event_id="ev-003", summary="Strategy Session")
    with _patch_calendar([event]):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await sync_calendar(config, conn)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        row = await (await conn.execute("SELECT payload FROM jobs")).fetchone()

    assert row is not None
    alias = row[0]["source_alias"]
    assert alias.endswith(".md")
    assert "Strategy_Session" in alias
    assert "primary" in alias
    assert "ev-003" in alias


async def test_sync_calendar_staged_filename_includes_event_id(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["google_calendar"],
            "google_calendar": GoogleCalendarConnectorConfig(staging_dir=staging_dir),
        }
    )

    event = _make_event(event_id="ev-unique-004", summary="Same Title")
    with _patch_calendar([event]):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await sync_calendar(config, conn)

    staged_files = list(staging_dir.glob("*.md"))
    assert any("ev-unique-004" in f.name for f in staged_files)


# ── recurring event identity ──────────────────────────────────────────────────

async def test_sync_calendar_recurring_instance_locator(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["google_calendar"],
            "google_calendar": GoogleCalendarConnectorConfig(
                staging_dir=tmp_path / "staging"
            ),
        }
    )

    event = _make_event(
        event_id="event-instance-1",
        summary="Weekly Standup",
        recurring_event_id="recurring-base-id",
        original_start_time="2026-05-13T10:00:00Z",
    )
    with _patch_calendar([event]):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await sync_calendar(config, conn)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        row = await (await conn.execute("SELECT payload FROM jobs")).fetchone()

    assert row is not None
    locator = row[0]["source_locator"]
    assert "recurring/recurring-base-id" in locator
    assert "instance/2026-05-13T10:00:00Z" in locator


# ── metadata contract ─────────────────────────────────────────────────────────

async def test_sync_calendar_metadata_contract(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["google_calendar"],
            "google_calendar": GoogleCalendarConnectorConfig(
                staging_dir=tmp_path / "staging"
            ),
        }
    )

    event = _make_event(
        event_id="ev-meta",
        calendar_id="primary",
        recurring_event_id="rec-base",
        original_start_time="2026-05-13T10:00:00Z",
        html_link="https://calendar.google.com/event?id=ev-meta",
    )
    with _patch_calendar([event]):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await sync_calendar(config, conn)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        row = await (await conn.execute("SELECT payload FROM jobs")).fetchone()

    assert row is not None
    meta = row[0]["metadata"]
    assert meta["connector"] == "google_calendar"
    assert meta["calendar_id"] == "primary"
    assert meta["event_id"] == "ev-meta"
    assert meta["recurring_event_id"] == "rec-base"
    assert meta["original_start_time"] == "2026-05-13T10:00:00Z"
    assert meta["html_link"] == "https://calendar.google.com/event?id=ev-meta"


# ── empty calendar ────────────────────────────────────────────────────────────

async def test_sync_calendar_returns_zero_counts_for_empty_calendar(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["google_calendar"],
            "google_calendar": GoogleCalendarConnectorConfig(
                staging_dir=tmp_path / "staging"
            ),
        }
    )

    with (
        patch("cos.services.calendar.build_calendar_service", return_value=MagicMock()),
        patch("cos.services.calendar.list_events", return_value=[]),
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await sync_calendar(config, conn)

    assert result == CalendarSyncResult(
        calendars_scanned=1,
        events_discovered=0,
        jobs_enqueued=0,
    )


async def test_sync_calendar_raises_degraded_error_when_calendar_fetch_fails(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["google_calendar"],
            "google_calendar": GoogleCalendarConnectorConfig(
                calendar_ids=["primary"],
                staging_dir=tmp_path / "staging",
            ),
        }
    )

    with (
        patch("cos.services.calendar.build_calendar_service", return_value=MagicMock()),
        patch(
            "cos.services.calendar.list_events",
            side_effect=RuntimeError("Calendar API unavailable"),
        ),
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            with patch("cos.services.calendar.logging.error") as mock_log_error:
                with pytest.raises(CalendarSyncDegradedError) as exc_info:
                    await sync_calendar(config, conn)

    assert exc_info.value.failed_calendars == ["primary"]
    assert exc_info.value.result == CalendarSyncResult(
        calendars_scanned=1,
        events_discovered=0,
        jobs_enqueued=0,
    )
    assert mock_log_error.call_count == 1


# ── integration: no-op second sync ───────────────────────────────────────────

async def test_second_sync_same_event_resolves_to_noop(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Unchanged event re-synced → one canonical source, no duplicate blob."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["google_calendar"],
            "google_calendar": GoogleCalendarConnectorConfig(staging_dir=staging_dir),
        }
    )

    event = _make_event(event_id="ev-noop", summary="Stable Event")

    # First sync
    with _patch_calendar([event]):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result1 = await sync_calendar(config, conn)

    assert result1.jobs_enqueued == 1

    # Process the first job
    from cos.services.jobs import process_next_ingest_job

    await process_next_ingest_job(TEST_DSN, config)

    # Second sync — same event, same content
    with _patch_calendar([event]):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result2 = await sync_calendar(config, conn)

    assert result2.jobs_enqueued == 1  # job enqueued again for unchanged check

    # Process the second job
    await process_next_ingest_job(TEST_DSN, config)

    # Only one source record should exist
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        source_count = await (
            await conn.execute(
                "SELECT COUNT(*) FROM sources WHERE source_type = 'google_calendar_event'"
            )
        ).fetchone()

    assert source_count == (1,)

"""Calendar connector service — staging, source identity, and job enqueue orchestration."""
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg
from googleapiclient.errors import HttpError

from cos.config import CosConfig, GoogleCalendarConnectorConfig
from cos.connectors.calendar import (
    CalendarEvent,
    build_calendar_service,
    list_events,
    normalise_event,
)
from cos.connectors.google_auth import AuthError
from cos.services.jobs import submit_ingest_job

_CONNECTOR = "google_calendar"


@dataclass
class CalendarSyncResult:
    calendars_scanned: int
    events_discovered: int
    jobs_enqueued: int


class CalendarSyncDegradedError(RuntimeError):
    """Raised when one or more configured calendars could not be synced."""

    def __init__(
        self,
        result: CalendarSyncResult,
        failed_calendars: list[str],
    ) -> None:
        self.result = result
        self.failed_calendars = failed_calendars
        joined = ", ".join(repr(calendar_id) for calendar_id in failed_calendars)
        super().__init__(f"failed calendars: {joined}")


async def sync_calendar(
    config: CosConfig,
    conn: psycopg.AsyncConnection[Any],
) -> CalendarSyncResult:
    """Fetch upcoming Calendar events, stage Markdown files, and enqueue ingest jobs."""
    cal_config = config.google_calendar or GoogleCalendarConnectorConfig()
    staging_dir = cal_config.staging_dir
    staging_dir.mkdir(parents=True, exist_ok=True)

    service = build_calendar_service(config)

    now = datetime.now(timezone.utc)
    time_min = now - timedelta(hours=cal_config.lookback_hours)
    time_max = now + timedelta(days=cal_config.lookahead_days)

    total_events = 0
    total_jobs = 0
    failed_calendars: list[str] = []

    for calendar_id in cal_config.calendar_ids:
        try:
            raw_events = list_events(service, calendar_id, time_min, time_max, cal_config)
        except HttpError as exc:
            failed_calendars.append(calendar_id)
            _log_connector_warning(
                f"Calendar API error for calendar {calendar_id!r}: {exc}"
            )
            continue
        except AuthError:
            raise
        except Exception as exc:
            failed_calendars.append(calendar_id)
            _log_connector_error(
                f"Unexpected error fetching calendar {calendar_id!r}: {exc}"
            )
            continue

        for raw_event in raw_events:
            try:
                event = normalise_event(raw_event, calendar_id)
            except Exception as exc:
                _log_connector_error(f"Failed to normalise event: {exc}")
                continue

            total_events += 1

            source_locator = _build_source_locator(event)
            source_alias = _build_source_alias(event)
            staged_path = _stage_event(event, staging_dir)
            metadata = _build_metadata(event)

            await submit_ingest_job(
                conn,
                staged_path=str(staged_path),
                source_type="google_calendar_event",
                source_locator=source_locator,
                source_alias=source_alias,
                metadata=metadata,
            )
            total_jobs += 1

    result = CalendarSyncResult(
        calendars_scanned=len(cal_config.calendar_ids),
        events_discovered=total_events,
        jobs_enqueued=total_jobs,
    )
    if failed_calendars:
        raise CalendarSyncDegradedError(result, failed_calendars)
    return result


def _build_source_locator(event: CalendarEvent) -> str:
    """Build a stable, canonical source locator for the event."""
    cal = _url_safe(event.calendar_id)
    if event.recurring_event_id and event.original_start_time:
        rec = _url_safe(event.recurring_event_id)
        ost = _url_safe(event.original_start_time)
        return (
            f"google-calendar://calendar/{cal}"
            f"/recurring/{rec}/instance/{ost}"
        )
    return f"google-calendar://calendar/{cal}/event/{_url_safe(event.event_id)}"


def _build_source_alias(event: CalendarEvent) -> str:
    """Build a human-readable, deterministic source alias ending in .md."""
    cal = _slug(event.calendar_id)
    title = _slug(event.summary) if event.summary else "untitled-event"
    ev = _slug(event.event_id)
    return f"{title}_{cal}_{ev}.md"


def _stage_event(event: CalendarEvent, staging_dir: Path) -> Path:
    """Render the event as Markdown and write it to the staging directory."""
    filename = f"{_slug(event.calendar_id)}_{_slug(event.event_id)}.md"
    staged_path = staging_dir / filename
    content = _format_event_md(event)
    staged_path.write_text(content, encoding="utf-8")
    return staged_path


def _format_event_md(event: CalendarEvent) -> str:
    lines = [f"# {event.summary or '(No title)'}"]
    lines.append("")
    lines.append(f"**Calendar:** {event.calendar_id}")
    lines.append(f"**Start:** {event.start}")
    lines.append(f"**End:** {event.end}")
    if event.is_all_day:
        lines.append("**Type:** All-day event")
    if event.organizer:
        lines.append(f"**Organiser:** {event.organizer}")
    if event.attendees:
        lines.append("**Attendees:**")
        for attendee in event.attendees:
            lines.append(f"  - {attendee}")
    if event.location:
        lines.append(f"**Location:** {event.location}")
    if event.status:
        lines.append(f"**Status:** {event.status}")
    if event.html_link:
        lines.append(f"**Link:** {event.html_link}")
    if event.description:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(event.description)
    return "\n".join(lines)


def _build_metadata(event: CalendarEvent) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "connector": _CONNECTOR,
        "calendar_id": event.calendar_id,
        "event_id": event.event_id,
        "status": event.status,
    }
    if event.recurring_event_id:
        meta["recurring_event_id"] = event.recurring_event_id
    if event.original_start_time:
        meta["original_start_time"] = event.original_start_time
    if event.html_link:
        meta["html_link"] = event.html_link
    return meta


def _url_safe(value: str) -> str:
    """Preserve the value as-is for use in URIs (colons etc. are valid in URI paths)."""
    return value


def _slug(value: str) -> str:
    """Convert a value to a filesystem-safe slug."""
    clean = re.sub(r"[^A-Za-z0-9._-]", "_", value)
    return clean[:80] or "unknown"


def _log_connector_error(message: str) -> None:
    logging.error(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "component": "connector",
                "connector": _CONNECTOR,
                "message": message,
                "recovery": "uv run cos auth calendar",
            }
        )
    )


def _log_connector_warning(message: str) -> None:
    logging.warning(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "WARNING",
                "component": "connector",
                "connector": _CONNECTOR,
                "message": message,
            }
        )
    )


def _log_connector_info(message: str) -> None:
    logging.info(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "component": "connector",
                "connector": _CONNECTOR,
                "message": message,
            }
        )
    )

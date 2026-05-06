"""Google Calendar API connector — event discovery, normalisation, and retry."""
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from googleapiclient.discovery import build as _google_build
from googleapiclient.errors import HttpError

from cos.config import CosConfig, GoogleCalendarConnectorConfig
from cos.connectors.google_auth import load_credentials

_TRANSIENT_HTTP_CODES = frozenset({429, 500, 502, 503, 504})
_RETRYABLE_403_REASONS = frozenset(
    {"ratelimitexceeded", "userratelimitexceeded", "quotaexceeded", "backenderror"}
)
_MAX_RETRIES = 5
_INITIAL_BACKOFF = 1.0


@dataclass
class CalendarEvent:
    event_id: str
    calendar_id: str
    summary: str
    start: str
    end: str
    is_all_day: bool
    attendees: list[str] = field(default_factory=list)
    organizer: str = ""
    description: str = ""
    html_link: str = ""
    location: str = ""
    status: str = ""
    recurring_event_id: str | None = None
    original_start_time: str | None = None


def get_calendar_credentials(config: CosConfig) -> Any:
    """Return valid Google Calendar credentials, refreshing locally when possible."""
    return load_credentials("google_calendar", config.google_oauth)


def build_calendar_service(config: CosConfig) -> Any:
    """Build an authenticated Calendar API service resource."""
    creds = get_calendar_credentials(config)
    return _google_build("calendar", "v3", credentials=creds, cache_discovery=False)


def list_events(
    service: Any,
    calendar_id: str,
    time_min: datetime,
    time_max: datetime,
    cal_config: GoogleCalendarConnectorConfig,
) -> list[dict[str, Any]]:
    """Return event resources for the given calendar and time window."""
    response = _execute_with_retry(
        service.events().list(
            calendarId=calendar_id,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=cal_config.max_results,
        )
    )
    return response.get("items", [])


def normalise_event(event: dict[str, Any], calendar_id: str) -> CalendarEvent:
    """Normalise a Calendar API event resource into a typed CalendarEvent."""
    raw_event_id = event.get("id")
    if not isinstance(raw_event_id, str) or not raw_event_id:
        raise ValueError("calendar event missing id")

    start_info = event.get("start", {})
    end_info = event.get("end", {})

    is_all_day = "date" in start_info and "dateTime" not in start_info
    start = start_info.get("dateTime") or start_info.get("date", "")
    end = end_info.get("dateTime") or end_info.get("date", "")

    attendees = [
        _format_person(a) for a in event.get("attendees", []) if isinstance(a, dict)
    ]

    organizer_info = event.get("organizer")
    organizer = _format_person(organizer_info) if isinstance(organizer_info, dict) else ""

    # Recurring instance fields
    recurring_event_id: str | None = event.get("recurringEventId")
    original_start_time: str | None = None
    raw_ost = event.get("originalStartTime")
    if isinstance(raw_ost, dict):
        original_start_time = raw_ost.get("dateTime") or raw_ost.get("date")

    return CalendarEvent(
        event_id=raw_event_id,
        calendar_id=calendar_id,
        summary=str(event.get("summary", "")),
        start=start,
        end=end,
        is_all_day=is_all_day,
        attendees=attendees,
        organizer=organizer,
        description=str(event.get("description", "")),
        html_link=str(event.get("htmlLink", "")),
        location=str(event.get("location", "")),
        status=str(event.get("status", "")),
        recurring_event_id=recurring_event_id,
        original_start_time=original_start_time,
    )


def _format_person(person: dict[str, Any]) -> str:
    name = person.get("displayName", "")
    email = person.get("email", "")
    if name and email:
        return f"{name} <{email}>"
    return email or name


def _execute_with_retry(request: Any) -> dict[str, Any]:
    """Execute a Calendar API request with exponential backoff on transient errors."""
    delay = _INITIAL_BACKOFF
    last_exc: HttpError | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            result: dict[str, Any] = request.execute()
            return result
        except HttpError as exc:
            if not _is_retryable_http_error(exc):
                raise
            last_exc = exc
            _log_connector_warning(
                f"retryable HTTP {exc.resp.status} "
                f"on attempt {attempt + 1}/{_MAX_RETRIES}"
            )
            if attempt < _MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
    raise last_exc  # type: ignore[misc]


def _is_retryable_http_error(exc: HttpError) -> bool:
    if exc.resp.status in _TRANSIENT_HTTP_CODES:
        return True
    if exc.resp.status != 403:
        return False

    try:
        payload = json.loads(exc.content.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return False

    candidates: list[str] = []
    error = payload.get("error")
    if isinstance(error, dict):
        for key in ("message", "status"):
            value = error.get(key)
            if isinstance(value, str):
                candidates.append(value.lower())
        errors = error.get("errors")
        if isinstance(errors, list):
            for item in errors:
                if not isinstance(item, dict):
                    continue
                reason = item.get("reason")
                if isinstance(reason, str):
                    candidates.append(reason.lower())

    candidate_text = " ".join(candidates)
    return bool(
        set(candidates) & _RETRYABLE_403_REASONS
        or "rate limit" in candidate_text
        or "quota" in candidate_text
    )


def _log_connector_warning(message: str) -> None:
    logging.warning(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "WARNING",
                "component": "connector",
                "connector": "google_calendar",
                "message": message,
            }
        )
    )

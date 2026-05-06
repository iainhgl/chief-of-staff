"""Tests for Google Calendar API connector: event normalisation, backoff."""
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from cos.config import GoogleCalendarConnectorConfig
from cos.connectors.calendar import (
    CalendarEvent,
    _execute_with_retry,
    _is_retryable_http_error,
    build_calendar_service,
    list_events,
    normalise_event,
)


def _http_error(status: int, content: bytes = b"error") -> HttpError:
    resp = MagicMock()
    resp.status = status
    return HttpError(resp=resp, content=content)


def _timed_event(
    event_id: str = "event-001",
    summary: str = "Board Sync",
    start: str = "2026-05-10T09:00:00+01:00",
    end: str = "2026-05-10T10:00:00+01:00",
    attendees: list[dict] | None = None,
    organizer: dict | None = None,
    description: str = "",
    html_link: str = "",
    status: str = "confirmed",
    recurring_event_id: str | None = None,
    original_start_time: dict | None = None,
) -> dict:
    event: dict = {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        "status": status,
    }
    if attendees is not None:
        event["attendees"] = attendees
    if organizer is not None:
        event["organizer"] = organizer
    if description:
        event["description"] = description
    if html_link:
        event["htmlLink"] = html_link
    if recurring_event_id is not None:
        event["recurringEventId"] = recurring_event_id
    if original_start_time is not None:
        event["originalStartTime"] = original_start_time
    return event


def _all_day_event(
    event_id: str = "event-allday",
    summary: str = "All-Day Event",
    start_date: str = "2026-05-12",
    end_date: str = "2026-05-13",
) -> dict:
    return {
        "id": event_id,
        "summary": summary,
        "start": {"date": start_date},
        "end": {"date": end_date},
        "status": "confirmed",
    }


# ── build_calendar_service ────────────────────────────────────────────────────

def test_build_calendar_service_uses_calendar_credentials() -> None:
    mock_creds = MagicMock()
    mock_service = MagicMock()
    with (
        patch("cos.connectors.calendar.get_calendar_credentials", return_value=mock_creds),
        patch("cos.connectors.calendar._google_build", return_value=mock_service) as mock_build,
    ):
        config = MagicMock()
        result = build_calendar_service(config)

    mock_build.assert_called_once_with(
        "calendar", "v3", credentials=mock_creds, cache_discovery=False
    )
    assert result is mock_service


# ── list_events ───────────────────────────────────────────────────────────────

def test_list_events_passes_correct_parameters() -> None:
    service = MagicMock()
    events_list = service.events.return_value.list.return_value
    events_list.execute.return_value = {"items": []}

    cfg = GoogleCalendarConnectorConfig()
    import datetime
    time_min = datetime.datetime(2026, 5, 10, 0, 0, tzinfo=datetime.timezone.utc)
    time_max = datetime.datetime(2026, 5, 24, 0, 0, tzinfo=datetime.timezone.utc)

    result = list_events(service, "primary", time_min, time_max, cfg)

    assert result == []
    service.events.return_value.list.assert_called_once()
    call_kwargs = service.events.return_value.list.call_args.kwargs
    assert call_kwargs["calendarId"] == "primary"
    assert call_kwargs["singleEvents"] is True
    assert call_kwargs["orderBy"] == "startTime"
    assert call_kwargs["maxResults"] == cfg.max_results


def test_list_events_returns_items() -> None:
    service = MagicMock()
    event = _timed_event("ev-1")
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [event]
    }

    cfg = GoogleCalendarConnectorConfig()
    import datetime
    time_min = datetime.datetime(2026, 5, 10, tzinfo=datetime.timezone.utc)
    time_max = datetime.datetime(2026, 5, 24, tzinfo=datetime.timezone.utc)

    result = list_events(service, "primary", time_min, time_max, cfg)
    assert len(result) == 1
    assert result[0]["id"] == "ev-1"


# ── normalise_event ───────────────────────────────────────────────────────────

def test_normalise_timed_event() -> None:
    event = _timed_event(
        event_id="ev-timed",
        summary="Q3 Review",
        start="2026-05-10T09:00:00+01:00",
        end="2026-05-10T10:00:00+01:00",
        attendees=[
            {"displayName": "Alice", "email": "alice@example.com"},
            {"displayName": "Bob", "email": "bob@example.com"},
        ],
        organizer={"displayName": "Charlie", "email": "charlie@example.com"},
        description="Quarterly review",
        html_link="https://calendar.google.com/event?id=ev-timed",
    )

    result = normalise_event(event, "primary")

    assert isinstance(result, CalendarEvent)
    assert result.event_id == "ev-timed"
    assert result.calendar_id == "primary"
    assert result.summary == "Q3 Review"
    assert result.start == "2026-05-10T09:00:00+01:00"
    assert result.end == "2026-05-10T10:00:00+01:00"
    assert result.is_all_day is False
    assert len(result.attendees) == 2
    assert result.organizer == "Charlie <charlie@example.com>"
    assert result.description == "Quarterly review"
    assert result.html_link == "https://calendar.google.com/event?id=ev-timed"
    assert result.recurring_event_id is None
    assert result.original_start_time is None


def test_normalise_all_day_event() -> None:
    event = _all_day_event(
        event_id="ev-allday",
        summary="Company Holiday",
        start_date="2026-05-12",
        end_date="2026-05-13",
    )

    result = normalise_event(event, "primary")

    assert result.event_id == "ev-allday"
    assert result.summary == "Company Holiday"
    assert result.start == "2026-05-12"
    assert result.end == "2026-05-13"
    assert result.is_all_day is True


def test_normalise_recurring_instance() -> None:
    event = _timed_event(
        event_id="event-recurring-instance-1",
        summary="Weekly Standup",
        start="2026-05-13T10:00:00Z",
        end="2026-05-13T10:30:00Z",
        recurring_event_id="recurring-base-id",
        original_start_time={"dateTime": "2026-05-13T10:00:00Z"},
    )

    result = normalise_event(event, "primary")

    assert result.recurring_event_id == "recurring-base-id"
    assert result.original_start_time == "2026-05-13T10:00:00Z"


def test_normalise_event_handles_missing_optional_fields() -> None:
    event = {
        "id": "ev-minimal",
        "summary": "",
        "start": {"dateTime": "2026-05-10T09:00:00Z"},
        "end": {"dateTime": "2026-05-10T10:00:00Z"},
        "status": "confirmed",
    }

    result = normalise_event(event, "primary")

    assert result.summary == ""
    assert result.attendees == []
    assert result.organizer == ""
    assert result.description == ""
    assert result.html_link == ""
    assert result.location == ""


def test_normalise_event_attendees_format() -> None:
    event = _timed_event(
        attendees=[
            {"displayName": "Alice", "email": "alice@example.com"},
            {"email": "noname@example.com"},
        ],
    )
    result = normalise_event(event, "primary")

    assert "Alice <alice@example.com>" in result.attendees
    assert "noname@example.com" in result.attendees


def test_normalise_event_rejects_missing_id() -> None:
    event = _timed_event()
    event.pop("id")

    with pytest.raises(ValueError, match="missing id"):
        normalise_event(event, "primary")


# ── retry / backoff ───────────────────────────────────────────────────────────

def test_execute_with_retry_succeeds_on_first_try() -> None:
    request = MagicMock()
    request.execute.return_value = {"items": []}
    assert _execute_with_retry(request) == {"items": []}
    request.execute.assert_called_once()


def test_execute_with_retry_retries_on_transient_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cos.connectors.calendar.time.sleep", lambda s: None)
    call_count = 0

    class _FakeRequest:
        def execute(self) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise _http_error(429)
            return {"items": []}

    result = _execute_with_retry(_FakeRequest())
    assert result == {"items": []}
    assert call_count == 3


def test_execute_with_retry_raises_on_non_transient_error() -> None:
    request = MagicMock()
    request.execute.side_effect = _http_error(404)
    with pytest.raises(HttpError):
        _execute_with_retry(request)


def test_execute_with_retry_exhausts_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cos.connectors.calendar.time.sleep", lambda s: None)
    request = MagicMock()
    request.execute.side_effect = _http_error(503)
    with pytest.raises(HttpError):
        _execute_with_retry(request)
    assert request.execute.call_count == 5


def test_is_retryable_http_error_transient_codes() -> None:
    for code in (429, 500, 502, 503, 504):
        assert _is_retryable_http_error(_http_error(code)) is True


def test_is_retryable_http_error_non_transient_codes() -> None:
    for code in (400, 401, 403, 404):
        # 403 is only retryable for specific reasons; generic 403 is not
        if code == 403:
            assert _is_retryable_http_error(_http_error(403)) is False
        else:
            assert _is_retryable_http_error(_http_error(code)) is False


def test_is_retryable_rate_limited_403() -> None:
    payload = (
        b'{"error":{"errors":[{"reason":"userRateLimitExceeded"}],'
        b'"message":"User rate limit exceeded"}}'
    )
    assert _is_retryable_http_error(_http_error(403, payload)) is True

"""
cal_client.py — Thin wrapper around the Cal.com v2 REST API.

Covers the four operations we need:
  • fetch available slots for an event type
  • create a booking
  • list bookings for a user
  • cancel a booking
  • reschedule a booking
"""

import os
import re
from datetime import datetime

import httpx
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

CAL_API_KEY = os.getenv("CAL_API_KEY", "")
CAL_BASE_URL = "https://api.cal.com/v2"
DEFAULT_EVENT_TYPE_ID = int(os.getenv("CAL_EVENT_TYPE_ID", "0"))
USER_NAME = os.getenv("CAL_USER_NAME", "")
USER_EMAIL = os.getenv("CAL_USER_EMAIL", "")
USER_TIMEZONE = os.getenv("CAL_TIMEZONE", "America/New_York")

# Regex for valid booking UIDs — alphanumeric plus hyphens only
_BOOKING_UID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _to_local_iso(dt_string: str) -> str:
    """Ensure a datetime string is in the user's configured timezone as ISO-8601.

    The LLM always sends times in CAL_TIMEZONE. We parse and re-format
    to a clean ISO-8601 string with the timezone offset so the Cal.com
    API knows exactly what time is meant.
    """
    if dt_string.endswith("Z"):
        dt_string = dt_string[:-1] + "+00:00"

    dt = datetime.fromisoformat(dt_string)
    local_tz = ZoneInfo(USER_TIMEZONE)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=local_tz)
    else:
        dt = dt.astimezone(local_tz)

    return dt.isoformat()


def check_config() -> list[str]:
    """Return a list of missing / invalid env-var warnings."""
    issues: list[str] = []
    if not CAL_API_KEY:
        issues.append("CAL_API_KEY is not set.")
    if DEFAULT_EVENT_TYPE_ID == 0:
        issues.append("CAL_EVENT_TYPE_ID is missing or zero.")
    if not USER_EMAIL:
        issues.append("CAL_USER_EMAIL is not set.")
    return issues

# shared headers for every request
_HEADERS = {
    "Authorization": f"Bearer {CAL_API_KEY}",
    "cal-api-version": "2026-02-25",
    "Content-Type": "application/json",
}


def _client() -> httpx.Client:
    """Return a pre-configured httpx client. We create a fresh one each call
    so there's no global mutable state to worry about."""
    return httpx.Client(base_url=CAL_BASE_URL, headers=_HEADERS, timeout=30)


# ── slots ────────────────────────────────────────────────────────────────────

def get_available_slots(start_date: str, end_date: str, event_type_id: int | None = None) -> dict:
    """
    Fetch open time slots between two dates (ISO format, e.g. '2025-04-01').
    Returns the raw JSON so the LLM can pick a slot to offer the user.
    """
    event_type_id = event_type_id or DEFAULT_EVENT_TYPE_ID
    params = {
        "start": start_date,
        "end": end_date,
        "eventTypeId": event_type_id,
        "timeZone": USER_TIMEZONE,
    }
    with _client() as c:
        resp = c.get("/slots", params=params, headers={"cal-api-version": "2026-02-25"})
        resp.raise_for_status()
        return resp.json()


# ── bookings ─────────────────────────────────────────────────────────────────

def create_booking(
    start_time: str,
    attendee_name: str | None = None,
    attendee_email: str | None = None,
    event_type_id: int | None = None,
    reason: str = "",
) -> dict:
    """
    Book a slot. `start_time` should be a full ISO-8601 datetime
    (e.g. '2025-04-10T14:00:00Z'). Attendee name/email default to
    the values in .env if not provided.
    """
    attendee_name = attendee_name or USER_NAME
    attendee_email = attendee_email or USER_EMAIL
    event_type_id = event_type_id or DEFAULT_EVENT_TYPE_ID
    local_start = _to_local_iso(start_time)
    body = {
        "start": local_start,
        "eventTypeId": event_type_id,
        "attendee": {
            "name": attendee_name,
            "email": attendee_email,
            "timeZone": USER_TIMEZONE,
        },
        "metadata": {},
    }
    if reason:
        body["metadata"]["notes"] = reason

    with _client() as c:
        resp = c.post("/bookings", json=body)
        resp.raise_for_status()
        return resp.json()


def list_bookings(email: str | None = None, status: str = "upcoming") -> dict:
    """
    Return bookings for the given e-mail. Status can be
    'upcoming', 'past', 'cancelled', or 'recurring'.
    """
    email = email or USER_EMAIL
    params: dict = {}
    if email:
        params["attendeeEmail"] = email
    if status:
        params["status"] = status

    with _client() as c:
        resp = c.get("/bookings", params=params)
        resp.raise_for_status()
        return resp.json()


def _validate_uid(uid: str) -> None:
    """Raise if a booking UID contains unexpected characters."""
    if not _BOOKING_UID_RE.match(uid):
        raise ValueError(f"Invalid booking UID: {uid!r}")


def cancel_booking(booking_uid: str, reason: str = "") -> dict:
    """Cancel an existing booking by its UID."""
    _validate_uid(booking_uid)
    body: dict = {}
    if reason:
        body["cancellationReason"] = reason

    with _client() as c:
        resp = c.post(f"/bookings/{booking_uid}/cancel", json=body)
        resp.raise_for_status()
        return resp.json()


def reschedule_booking(booking_uid: str, new_start_time: str, reason: str = "") -> dict:
    """Move an existing booking to a new time slot."""
    _validate_uid(booking_uid)
    local_start = _to_local_iso(new_start_time)
    body: dict = {
        "start": local_start,
        "reschedulingReason": reason,
    }
    with _client() as c:
        resp = c.post(f"/bookings/{booking_uid}/reschedule", json=body)
        resp.raise_for_status()
        return resp.json()

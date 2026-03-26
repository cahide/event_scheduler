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
from datetime import datetime, timedelta

import httpx
from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import pytz

load_dotenv()

CAL_API_KEY = os.getenv("CAL_API_KEY", "")
CAL_BASE_URL = "https://api.cal.com/v2"
DEFAULT_EVENT_TYPE_ID = int(os.getenv("CAL_EVENT_TYPE_ID", "0"))
USER_EMAIL = os.getenv("CAL_USER_EMAIL", "")
USER_TIMEZONE = os.getenv("CAL_TIMEZONE", "America/New_York")

# Regex for valid booking UIDs — alphanumeric plus hyphens only
_BOOKING_UID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def parse_date_string(date_input: str, time_input: str = "14:00") -> str:
    """
    Parse natural language or formatted date/time and return ISO-8601 datetime.
    
    Handles:
    - Natural dates: "tomorrow", "next monday", "3 days from now"
    - Multiple formats: "2025-04-10", "10/04/2025", "April 10", "10.04.2025"
    - With time: "2025-04-10 14:30" or separate time_input parameter
    
    Returns ISO-8601 datetime string (e.g. '2025-04-10T14:30:00Z')
    """
    user_tz = pytz.timezone(USER_TIMEZONE)
    now = datetime.now(user_tz)
    
    # Convert to lowercase for natural language detection
    date_lower = date_input.lower().strip()
    
    # Natural language date handling
    natural_phrases = {
        "tomorrow": now + timedelta(days=1),
        "today": now,
        "next week": now + timedelta(weeks=1),
        "next monday": now + relativedelta(weekday=0, weeks=+1),
        "next tuesday": now + relativedelta(weekday=1, weeks=+1),
        "next wednesday": now + relativedelta(weekday=2, weeks=+1),
        "next thursday": now + relativedelta(weekday=3, weeks=+1),
        "next friday": now + relativedelta(weekday=4, weeks=+1),
        "next saturday": now + relativedelta(weekday=5, weeks=+1),
        "next sunday": now + relativedelta(weekday=6, weeks=+1),
    }
    
    # Check for natural language phrases
    for phrase, date_obj in natural_phrases.items():
        if phrase in date_lower:
            # Extract time if embedded in the string
            time_part = time_input
            for potential_time in re.findall(r'\d{1,2}[:.]?\d{2}', date_input):
                time_part = potential_time.replace(".", ":")
                break
            
            hour, minute = map(int, time_part.split(":"))
            date_obj = date_obj.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return date_obj.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")
    
    # Try parsing as a standard date/time format
    try:
        # If there's a time embedded, use it
        if " " in date_input and re.search(r'\d{1,2}[:\.]\d{2}', date_input):
            parsed = dateutil_parser.parse(date_input, dayfirst=True)
        else:
            # Parse date and add the time_input
            parsed = dateutil_parser.parse(date_input, dayfirst=True)
            hour, minute = map(int, time_input.split(":"))
            parsed = parsed.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Localize to user timezone
        if parsed.tzinfo is None:
            parsed = user_tz.localize(parsed)
        
        # Convert to UTC and format as ISO-8601
        return parsed.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")
    except Exception:
        raise ValueError(
            f"Could not parse date '{date_input}' with time '{time_input}'. "
            "Try 'tomorrow at 14:00', '2025-04-10 15:30', or 'April 15, 2025'"
        )


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
    "cal-api-version": "2024-08-13",
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
        "startTime": start_date,
        "endTime": end_date,
        "eventTypeId": event_type_id,
    }
    with _client() as c:
        resp = c.get("/slots/available", params=params)
        resp.raise_for_status()
        return resp.json()


# ── bookings ─────────────────────────────────────────────────────────────────

def create_booking(
    start_time: str,
    attendee_name: str,
    attendee_email: str,
    event_type_id: int | None = None,
    reason: str = "",
) -> dict:
    """
    Book a slot. `start_time` should be a full ISO-8601 datetime
    (e.g. '2025-04-10T14:00:00Z'). The attendee fields describe the
    person being invited.
    """
    event_type_id = event_type_id or DEFAULT_EVENT_TYPE_ID
    body = {
        "start": start_time,
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
    body: dict = {
        "start": new_start_time,
        "reschedulingReason": reason,
    }
    with _client() as c:
        resp = c.post(f"/bookings/{booking_uid}/reschedule", json=body)
        resp.raise_for_status()
        return resp.json()

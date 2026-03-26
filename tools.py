"""
tools.py — OpenAI function-calling tool definitions + dispatch logic.

Each tool maps to one cal_client function. The TOOLS list is passed straight
to the OpenAI chat completions API so it knows what it can call.
"""

import json

import cal_client

# ── tool schemas (OpenAI function-calling format) ────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": (
                "Look up open calendar slots for a given date range. "
                "Use this before booking to make sure the time works."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start of the range, ISO date like '2025-04-01'.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End of the range, ISO date like '2025-04-02'.",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_booking",
            "description": (
                "Book a meeting on a specific date and time. You can use natural language "
                "for dates like 'tomorrow', 'next monday', or formats like '2025-04-10', "
                "'April 15, 2025', etc. Time defaults to 14:00 if not specified."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": (
                            "The date in any format or natural language. Examples: "
                            "'tomorrow', 'next monday', '2025-04-10', "
                            "'April 15', '15/04/2025', '2025-04-10 15:30', or just 'April 15'"
                        ),
                    },
                    "time": {
                        "type": "string",
                        "description": "Time in HH:MM format, e.g. '14:00' or '15:30'. Defaults to '14:00'.",
                    },
                    "attendee_name": {
                        "type": "string",
                        "description": "Name of the person attending.",
                    },
                    "attendee_email": {
                        "type": "string",
                        "description": "Email of the attendee.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional note or reason for the meeting.",
                    },
                },
                "required": ["date", "attendee_name", "attendee_email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_bookings",
            "description": (
                "List the user's scheduled events. Can filter by status: "
                "'upcoming', 'past', 'cancelled', or 'recurring'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["upcoming", "past", "cancelled", "recurring"],
                        "description": "Which bookings to show. Defaults to 'upcoming'.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_booking",
            "description": (
                "Cancel an existing booking. Requires the booking UID. "
                "If the user describes a booking by time or title, list bookings "
                "first to find the right UID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_uid": {
                        "type": "string",
                        "description": "The unique ID of the booking to cancel.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional cancellation reason.",
                    },
                },
                "required": ["booking_uid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_booking",
            "description": (
                "Move an existing booking to a different time. "
                "Needs the booking UID and the new start time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_uid": {
                        "type": "string",
                        "description": "UID of the booking to reschedule.",
                    },
                    "new_start_time": {
                        "type": "string",
                        "description": "New start time in ISO-8601 format.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional reason for rescheduling.",
                    },
                },
                "required": ["booking_uid", "new_start_time"],
            },
        },
    },
]


# ── dispatcher ───────────────────────────────────────────────────────────────
# maps function name → actual python callable

_DISPATCH = {
    "get_available_slots": cal_client.get_available_slots,
    "create_booking": cal_client.create_booking,
    "list_bookings": cal_client.list_bookings,
    "cancel_booking": cal_client.cancel_booking,
    "reschedule_booking": cal_client.reschedule_booking,
}


def run_tool(name: str, arguments: str) -> str:
    """
    Execute a tool call that came back from the model.
    `arguments` is the raw JSON string from the API response.
    Returns a JSON string with the result (or an error message).
    """
    fn = _DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        kwargs = json.loads(arguments)
        
        # Special handling for create_booking: convert date/time to start_time
        if name == "create_booking" and "date" in kwargs:
            date_str = kwargs.pop("date")
            time_str = kwargs.pop("time", "14:00")
            
            # Import here to avoid circular imports
            from cal_client import parse_date_string
            
            start_time = parse_date_string(date_str, time_str)
            kwargs["start_time"] = start_time
        
        result = fn(**kwargs)
        return json.dumps(result, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})

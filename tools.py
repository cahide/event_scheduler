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
                "Book a meeting at a specific time. The user's name and email "
                "are filled in automatically — only the start time and an "
                "optional reason are needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "Datetime in the user's local timezone (from system prompt), e.g. '2025-04-10T14:00:00'. Do NOT append 'Z'.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional note or reason for the meeting.",
                    },
                },
                "required": ["start_time"],
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
                        "description": "New start time in user's local timezone, e.g. '2025-04-10T14:00:00'. Do NOT append 'Z'.",
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
        result = fn(**kwargs)
        return json.dumps(result, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})

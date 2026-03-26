"""
chatbot.py — Core conversation loop powered by OpenAI function calling.

Keeps a running message history and automatically executes any tool calls
the model asks for, feeding the results back until the model produces a
final text reply for the user.
"""

import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from tools import TOOLS, run_tool

load_dotenv()

_api_key = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=_api_key) if _api_key else None

MODEL = "gpt-4o"
MAX_TOOL_ROUNDS = 10

_SYSTEM_PROMPT_TEMPLATE = """You are a friendly scheduling assistant that helps people manage their calendar through cal.com.

Today's date is {today}.

What you can do:
- Check available time slots and book meetings
- Show upcoming (or past / cancelled) events
- Cancel or reschedule existing bookings

Smart date handling:
- Users can say "tomorrow", "next monday", etc.
- They can use any date format: "2025-04-10", "April 15, 2025", "15/04/2025", etc.
- They can combine date and time: "2025-04-10 15:30" or specify time separately
- Default time is 14:00 if not specified

Guidelines:
- When the user wants to book a meeting, ask for: the date (you can accept natural language like "tomorrow"), time (or suggest 14:00), their name, their email, and optionally a reason.
- Always check available slots before booking so you don't suggest a taken time.
- When cancelling or rescheduling, list bookings first to find the correct UID — never guess.
- Keep answers concise and conversational.
- If something goes wrong with the API, let the user know in plain language and suggest what they can try.
"""


def _system_prompt() -> str:
    """Build the system prompt with today's actual date."""
    return _SYSTEM_PROMPT_TEMPLATE.format(
        today=datetime.now().strftime("%A, %B %d, %Y")
    )


def build_initial_messages() -> list[dict]:
    """Start a fresh conversation with the system prompt."""
    return [{"role": "system", "content": _system_prompt()}]


def chat(messages: list[dict], user_input: str) -> str:
    """
    Send the user's message, handle any tool calls the model makes,
    and return the final assistant text.

    `messages` is mutated in place so the caller keeps full history.
    """
    messages.append({"role": "user", "content": user_input})

    if client is None:
        return (
            "**No OpenAI API key found.** To actually talk to the assistant, "
            "add your key to the `.env` file:\n\n"
            "```\nOPENAI_API_KEY=sk-...\n```\n\n"
            "Then restart the server. For now you can still browse the UI!"
        )

    try:
        return _run_conversation(messages)
    except Exception as exc:
        return f"Something went wrong talking to OpenAI: {exc}"


async def chat_async(messages: list[dict], user_input: str) -> str:
    """Async wrapper so Chainlit's event loop isn't blocked."""
    return await asyncio.to_thread(chat, messages, user_input)


def _run_conversation(messages: list[dict]) -> str:
    """Inner loop that actually calls the API. Separated so we can
    catch errors cleanly in chat()."""
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        choice = response.choices[0]
        assistant_msg = choice.message

        # add the assistant's reply (text or tool calls) to history
        messages.append(assistant_msg.model_dump())

        # if the model didn't ask to call any tools, we're done
        if not assistant_msg.tool_calls:
            return assistant_msg.content or ""

        # otherwise, execute each tool and feed results back
        for call in assistant_msg.tool_calls:
            result = run_tool(call.function.name, call.function.arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                }
            )
        # loop back so the model can process the tool results

    return "I hit my limit on tool calls for this turn. Could you try again or simplify the request?"


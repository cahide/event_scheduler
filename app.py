"""
app.py — Chainlit front-end for the cal.com scheduling chatbot.

Run with:
    chainlit run app.py -w

Each browser session gets its own conversation history, so multiple
users can chat at the same time without stepping on each other.
"""

import chainlit as cl

import os

from dotenv import load_dotenv

from cal_client import check_config
from chatbot import build_initial_messages, chat_async

load_dotenv()
_USER_NAME = os.getenv("CAL_USER_NAME", "there")


@cl.on_chat_start
async def start():
    """Fires when a new user opens the chat. We stash a fresh message
    history in the session so every tab has its own context."""
    # warn early if env vars are missing
    issues = check_config()
    if issues:
        await cl.Message(
            content=(
                "**Configuration issues detected:**\n\n"
                + "\n".join(f"- {i}" for i in issues)
                + "\n\nPlease fix your `.env` file and restart."
            )
        ).send()
        return

    cl.user_session.set("messages", build_initial_messages())
    await cl.Message(
        content=(
            f"Hey {_USER_NAME}! I'm your scheduling assistant. I can help you:\n\n"
            "- **Book** a new meeting\n"
            "- **List** your upcoming events\n"
            "- **Cancel** or **reschedule** an event\n\n"
            "What would you like to do?"
        )
    ).send()


@cl.on_message
async def handle_message(message: cl.Message):
    """Called every time the user sends a message."""
    messages = cl.user_session.get("messages")

    # show a thinking indicator while we talk to OpenAI + cal.com
    async with cl.Step(name="Thinking..."):
        reply = await chat_async(messages, message.content)

    await cl.Message(content=reply).send()

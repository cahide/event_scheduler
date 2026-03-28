# Cal.com Scheduling Chatbot

A conversational scheduling assistant built with **OpenAI function calling** and the **Cal.com v2 API**.  
Users interact through a clean **Chainlit** web UI to book meetings, view their calendar, cancel events, and reschedule — all through natural language.

---

## Features

| Feature | Status |
|---|---|
| Book a new meeting (checks availability first) | Done |
| List upcoming / past / cancelled events | Done |
| Cancel an existing booking | Done |
| Reschedule a booking to a new time | Done |
| Interactive web UI (Chainlit) | Done |

---

## Project Structure

```
.
├── app.py            # Chainlit UI — the entry point you run
├── chatbot.py        # Conversation loop & OpenAI integration
├── tools.py          # Function-calling tool definitions + dispatcher
├── cal_client.py     # Thin wrapper around the Cal.com v2 REST API
├── requirements.txt  # Python dependencies
├── .env.example      # Template for environment variables
└── .gitignore
```

### How it works

1. **app.py** starts a Chainlit server. Each browser tab gets its own chat session.
2. When the user types a message, **chatbot.py** sends it to OpenAI's `gpt-4o` model along with the tool definitions from **tools.py**.
3. If the model decides it needs data (e.g. "check available slots"), it returns a `tool_call`. The dispatcher in **tools.py** routes that call to the matching function in **cal_client.py**, which hits the Cal.com API.
4. The API result is fed back into the conversation, and the model produces a human-friendly reply.
5. This loop repeats until the model has everything it needs and responds with plain text.

---

## Prerequisites

- **Python 3.11+**
- A **Cal.com** account with an API key ([how to get one](https://cal.com/docs/enterprise-features/api/authentication))
- An **OpenAI** API key with access to `gpt-4o`

---

## Setup

### 1. Clone and install

```bash
git clone event-scheduler
cd event-scheduler
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment variables

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

Open `.env` and set:

| Variable | What it is |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `CAL_API_KEY` | Cal.com API key (Bearer token for v2 API) |
| `CAL_USER_NAME` | Your name (used for bookings and greeting) |
| `CAL_USER_EMAIL` | The email tied to your Cal.com account |
| `CAL_EVENT_TYPE_ID` | Numeric ID of the event type to book (find it in your Cal.com event type URL) |
| `CAL_TIMEZONE` | Your timezone in IANA format (e.g. `America/Los_Angeles`, `Europe/London`) |

### 3. Run

```bash
chainlit run app.py -w
```

The `-w` flag enables hot-reload so changes to your code show up immediately.  
Open **http://localhost:8000** in your browser and start chatting.

---

## Usage Examples

**Booking a meeting**
> "Help me book a meeting tomorrow at 2pm"  
The bot will ask for the attendee's name, email, and reason, check available slots, and then create the booking.

**Listing events**
> "Show me my upcoming events"  
Returns a summary of all scheduled bookings.

**Cancelling**
> "Cancel my 3pm meeting today"  
The bot lists your bookings, identifies the right one, and cancels it.

**Rescheduling**
> "Move my Friday meeting to Monday at 10am"  
Finds the booking, checks the new slot, and reschedules.

---

## Tech Stack

- **Python 3.11+**
- **OpenAI API** — GPT-4o with function calling for intent detection and tool orchestration
- **Cal.com v2 API** — Calendar operations (slots, bookings, cancellations)
- **Chainlit** — Web UI framework for LLM-powered chat apps
- **httpx** — HTTP client for API calls
- **python-dotenv** — Environment variable management

---

## Notes

- The system prompt includes today's date so the model can resolve relative dates like "tomorrow" or "next Monday".
- Each Chainlit session maintains its own conversation history — multiple users can chat at the same time.
- API errors are caught and returned as plain-English messages so the user isn't hit with raw stack traces.

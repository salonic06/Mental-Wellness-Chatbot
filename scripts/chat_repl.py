"""
Local chat tester — talk to the bot in your terminal, no WhatsApp needed.

It drives the SAME router the WhatsApp webhook uses (bot_router.process_message),
so you can test /vent, /affirmation, /summary, /checkin, crisis handling, etc.,
with the real Gemini brain (or fallbacks if the LLM is off).

Run:
    py scripts/chat_repl.py

Type messages like a user. Special: 'quit' or 'exit' to leave.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env", override=True)

from bot_router import process_message  # noqa: E402
from database import init_db  # noqa: E402
from llm_client import status as llm_status  # noqa: E402
from state_store import clear_user_state  # noqa: E402

SENDER = "919999999999"  # a fake local test user


def main() -> None:
    init_db()
    # Each REPL session starts fresh — avoids leftover "venting" state in wellness.db
    # from a previous run (which made /start look broken).
    clear_user_state(SENDER)
    print(f"LLM: {llm_status()}")
    print(
        "Chat with your bot (type 'quit' to exit).\n"
        "Try: /start, /vent, /affirmation, /summary\n"
        "Tip: if stuck in a flow, type /cancel or /done.\n"
    )
    while True:
        try:
            text = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.lower() in ("quit", "exit"):
            break
        if not text:
            continue
        reply = process_message(SENDER, text)
        print(f"bot > {reply.text}\n")


if __name__ == "__main__":
    main()

"""
Live smoke test for the LLM brain.

Loads .env, prints provider status, then exercises the three wellness
functions with a throwaway demo user. Run:

    py scripts/llm_smoke.py

Costs: on Google's Gemini free tier this makes ~4 small requests and is free
(well within 1,500 requests/day). If the LLM is not configured, it reports the
deterministic fallbacks instead.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env", override=True)

from datetime import datetime  # noqa: E402

import db_paths  # noqa: E402
import llm_client  # noqa: E402
import llm_wellness  # noqa: E402
from database import init_db  # noqa: E402

DEMO_USER = "demo-smoke-user"


def _seed_demo_history() -> None:
    """Insert a little recent history so context + weekly summary have data."""
    conn = db_paths.connect()
    c = conn.cursor()
    c.execute("DELETE FROM mood_logs WHERE user_phone = ?", (DEMO_USER,))
    c.execute("DELETE FROM checkins WHERE user_phone = ?", (DEMO_USER,))
    now = datetime.now()
    for intensity, note in [(4, "work deadlines piling up"), (6, "gym helped"), (7, "good chat with a friend")]:
        c.execute(
            "INSERT INTO mood_logs (user_phone, mood, intensity, timestamp, notes) "
            "VALUES (?, 'checkin', ?, ?, ?)",
            (DEMO_USER, intensity, now, note),
        )
    c.execute(
        "INSERT INTO checkins (user_phone, intensity, category, note, created_at) "
        "VALUES (?, 5, 'work', 'deadlines', ?)",
        (DEMO_USER, now),
    )
    conn.commit()
    conn.close()


def _cleanup_demo_history() -> None:
    conn = db_paths.connect()
    c = conn.cursor()
    c.execute("DELETE FROM mood_logs WHERE user_phone = ?", (DEMO_USER,))
    c.execute("DELETE FROM checkins WHERE user_phone = ?", (DEMO_USER,))
    conn.commit()
    conn.close()


def main() -> int:
    init_db()  # ensure tables exist so context lookups don't error
    _seed_demo_history()
    print("=== LLM status ===")
    status = llm_client.status()
    print(status)
    if not status["enabled"]:
        print(
            "\nLLM is DISABLED. Set LLM_PROVIDER=gemini and LLM_API_KEY in .env, "
            "then re-run. (The bot still works using rule-based fallbacks.)"
        )
        _cleanup_demo_history()
        return 1

    print("\n=== 1) Raw generate() ===")
    out = llm_client.generate(
        "You are a friendly assistant. Reply in one short sentence.",
        "Say hello and confirm you are working.",
    )
    print(out or "(no output / call failed)")

    print("\n=== 2) Empathetic /vent reply ===")
    vent = llm_wellness.empathetic_vent_reply(
        "Work was horrible today, my manager dumped three deadlines on me.",
        "strong_negative",
        DEMO_USER,
    )
    print(vent or "(fell back to rule-based)")

    print("\n=== 3) Personalized affirmation ===")
    aff = llm_wellness.personalized_affirmation(DEMO_USER)
    print(aff or "(fell back to random affirmation)")

    print("\n=== 4) Weekly summary (from seeded demo history) ===")
    print(llm_wellness.weekly_summary_text(DEMO_USER))

    _cleanup_demo_history()
    print("\nDone. If you saw natural-language replies above, Gemini is wired in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

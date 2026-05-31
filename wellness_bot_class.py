import json
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
import random
import sqlite3

from db_paths import connect

logger = logging.getLogger(__name__)

load_dotenv()


def _digits_only(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())


class WellnessBot:
    def __init__(self):
        self.timezone = os.environ.get("TIMEZONE", "UTC")
        self.admin_numbers = [
            _digits_only(n)
            for n in os.environ.get("ADMIN_NUMBERS", "").split(",")
            if n.strip()
        ]

        self._load_json_data()
        if not self.affirmations:
            logger.warning("Affirmations list is empty. Please check affirmations.json")

    def _load_json_data(self):
        self.meditations = {}
        self.vent_instructions = {}
        self.breathing_patterns = {}
        self.affirmations = []  # Initialize as an empty list
        json_files = ['meditations.json', 'vent_instructions.json', 'breathing_exercises.json', 'affirmations.json']

        for file in json_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if file == 'meditations.json':
                        self.meditations = data
                    elif file == 'vent_instructions.json':
                        self.vent_instructions = data
                    elif file == 'breathing_exercises.json':
                        self.breathing_patterns = data
                    elif file == 'affirmations.json':
                        self.affirmations = data  # load affirmations from the new file

            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Error loading JSON file {file}: {e}")




    def start_command(self, args, sender):
        self._add_user_to_db(sender)  # Add user to the database
        return ("Welcome to your Mental Wellness Buddy! 🌟\n\n"
                "I'm here to support your mental well-being. Here's how I can help:\n"
                "- Track your mood with /mood\n"
                "- Get guided breathing exercises with /breathe\n"
                "- Receive daily affirmations with /affirmation\n"
                "- Start a meditation session with /meditate\n"
                "- Share your feelings with /vent\n"
                "- Do a guided check-in with /checkin\n"
                "- Opt into a daily check-in reminder with /remind on\n"
                "Type /help anytime to see all commands.")

    def _add_user_to_db(self, phone_number):
        try:
            conn = connect()
            c = conn.cursor()
            c.execute('INSERT OR IGNORE INTO users (phone_number, joined_date) VALUES (?, ?)',
                      (phone_number, datetime.now()))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error adding user to DB: {e}")

    def log_mood(self, args, sender):
        if not args:
            return ("How are you feeling? Rate your mood from 1-10 and add a note:\n"
                    "Example: /mood 7 feeling optimistic today")

        try:
            parts = args.split(' ', 1)
            intensity = int(parts[0])
            notes = parts[1] if len(parts) > 1 else ''

            if not 1 <= intensity <= 10:
                return "Please rate your mood between 1 and 10."

            if notes:
                from sentiment_nlp import detect_crisis, handle_crisis

                if detect_crisis(notes):
                    return handle_crisis(sender, notes, source="mood", intensity=intensity)

            conn = connect()
            c = conn.cursor()
            c.execute('''INSERT INTO mood_logs (user_phone, mood, intensity, timestamp, notes)
                        VALUES (?, ?, ?, ?, ?)''',
                      (sender, 'mood_log', intensity, datetime.now(), notes))
            conn.commit()
            conn.close()

            response = "Thanks for sharing! 📝\n"
            if intensity <= 3:
                response += (
                    "I'm sorry to hear you're feeling so low.  It's important to reach out for support. Would you like to:\n"
                    "- Try a breathing exercise? (/breathe)\n"
                    "- Talk about it? (/vent)\n"
                    "- Get an affirmation? (/affirmation)")
            elif intensity <= 5:
                response += ("I notice you're not feeling your best. Would you like to:\n"
                             "- Try a breathing exercise? (/breathe)\n"
                             "- Talk about it? (/vent)\n"
                             "- Get an affirmation? (/affirmation)")
            elif intensity <= 7:
                response += (
                    "It sounds like you're feeling somewhat down.  Remember that it's okay to not be okay.  Would you like to try a meditation? (/meditate)")
            else:
                response += (
                    "That's great to hear! Let's keep that positive feeling going.  How about trying a guided meditation to enhance your good mood? (/meditate)")


            return response

        except ValueError:
            return "Invalid input. Please enter a number between 1 and 10 followed by optional notes."
        except Exception as e:
            logger.error(f"Error logging mood: {e}")
            return "Sorry, there was an error logging your mood. Please try again later."

    def breathing_exercise(self, args, sender):
        if not args.strip():
            lines = [
                f"/breathe {name} — {info.get('description', '')}"
                for name, info in self.breathing_patterns.items()
            ]
            return "Choose a breathing pattern:\n" + "\n".join(lines)

        pattern_name = args.lower().split()[0]
        if pattern_name not in self.breathing_patterns:
            return "Pattern not found. Use: /breathe calm | relaxation | energize"
        pattern = self.breathing_patterns[pattern_name]
        return (
            f"*{pattern_name.title()} breathing*\n"
            f"Inhale {pattern['inhale']}s · hold {pattern['hold']}s · exhale {pattern['exhale']}s\n"
            f"Repeat {pattern['rounds']} rounds at your own pace."
        )

    def clear_active_meditation(self, sender: str) -> None:
        try:
            conn = connect()
            c = conn.cursor()
            c.execute("DELETE FROM active_meditations WHERE user_phone = ?", (sender,))
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error("Error clearing meditation: %s", e)

    @staticmethod
    def _meditation_script_keys(meditation: dict) -> list:
        intervals = meditation.get("intervals") or []
        if intervals:
            return [str(i) for i in sorted(intervals)]
        return sorted(meditation.get("script", {}).keys(), key=lambda k: int(k))

    def _meditation_pacing_hint(self, meditation: dict, step_index: int, keys: list) -> str:
        if step_index >= len(keys) - 1:
            return "\n\nType **end** when you are finished."

        intervals = meditation.get("intervals") or []
        try:
            from meditation_scheduler import nudges_enabled

            if nudges_enabled() and step_index < len(keys) - 1 and len(intervals) > step_index + 1:
                gap = intervals[step_index + 1] - intervals[1]
                if gap > 0:
                    return (
                        f"\n\nNext part arrives automatically in ~{gap} minute(s) "
                        "(or type **next** to skip ahead)."
                    )
        except ImportError:
            pass

        if step_index < len(intervals) - 1:
            gap = intervals[step_index + 1] - intervals[step_index]
            if gap > 0:
                return f"\n\nPause ~{gap} minute(s), then type **next** for the following part."
        return "\n\nType **next** when you are ready for the following part."

    def meditation_guide(self, args, sender):
        if not args.strip():
            options = [
                f"/meditate {key} — {value['duration']} min ({len(self._meditation_script_keys(value))} parts)"
                for key, value in self.meditations.items()
            ]
            return "Choose your meditation:\n" + "\n".join(options)

        meditation_type = args.lower().split()[0]
        if meditation_type not in self.meditations:
            return "Invalid type. Use: /meditate quick | medium | long"

        selected = self.meditations[meditation_type]
        keys = self._meditation_script_keys(selected)
        intro = selected["script"].get(keys[0], "Let's begin.")

        conn = connect()
        c = conn.cursor()
        try:
            c.execute(
                """INSERT OR REPLACE INTO active_meditations
                   (user_phone, meditation_type, start_time, paused, step_index)
                   VALUES (?, ?, NULL, 0, 0)""",
                (sender, meditation_type),
            )
            c.execute(
                """INSERT INTO meditation_sessions (user_phone, duration, type, started_at)
                   VALUES (?, ?, ?, ?)""",
                (sender, selected["duration"], meditation_type, datetime.now()),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Database error logging meditation session: %s", e)
            conn.rollback()
        finally:
            conn.close()

        return (
            f"{intro}\n\n"
            f"*{selected['duration']}-minute session · {len(keys)} parts*\n"
            f"Type **ready** to begin — the next parts arrive automatically "
            f"(~{selected['duration']} min session).\n"
            "Or type **next** to skip ahead. **pause** / **resume** control timers.\n"
            "**pause** · **resume** · **end** · **status**"
        )

    def handle_meditation_progress(self, message, sender):
        conn = connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """SELECT meditation_type, start_time, paused, step_index
                   FROM active_meditations WHERE user_phone = ?""",
                (sender,),
            )
            row = cursor.fetchone()

            if row is None:
                return "You haven't started a meditation session yet. Use /meditate to begin."

            meditation_type, start_time, paused, step_index = row
            step_index = step_index or 0
            meditation = self.meditations.get(meditation_type)
            if not meditation:
                cursor.execute("DELETE FROM active_meditations WHERE user_phone = ?", (sender,))
                conn.commit()
                return f"Error: Meditation type '{meditation_type}' not found."

            keys = self._meditation_script_keys(meditation)
            script = meditation.get("script", {})
            msg = message.lower().strip()

            if msg == "status":
                return (
                    f"Session: {meditation_type} ({meditation['duration']} min)\n"
                    f"Part {step_index + 1} of {len(keys)}"
                    + (" · paused" if paused else "")
                )

            if msg == "end":
                cursor.execute("DELETE FROM active_meditations WHERE user_phone = ?", (sender,))
                conn.commit()
                return "Meditation ended. Thank you. Type /mood to log how you feel."

            if msg == "pause":
                cursor.execute(
                    "UPDATE active_meditations SET paused = 1 WHERE user_phone = ?", (sender,)
                )
                conn.commit()
                return "Paused. Type **resume** or **end**."

            if msg == "resume":
                cursor.execute(
                    "UPDATE active_meditations SET paused = 0 WHERE user_phone = ?", (sender,)
                )
                conn.commit()
                return (
                    "Resumed. The next part arrives in ~1 minute per step "
                    "(or type **next** / **end**)."
                )

            if paused:
                return "Session is paused. Type **resume** or **end**."

            if msg in ("ready", "next"):
                if msg == "ready" and step_index > 0:
                    return "Session already started. Type **next** for the next part."

                new_step = 1 if msg == "ready" else step_index + 1
                if new_step >= len(keys):
                    cursor.execute(
                        "DELETE FROM active_meditations WHERE user_phone = ?", (sender,)
                    )
                    conn.commit()
                    return (
                        script.get(keys[-1], "Well done.")
                        + "\n\nSession complete. Type /mood to log how you feel."
                    )

                if msg == "ready" and not start_time:
                    cursor.execute(
                        "UPDATE active_meditations SET start_time = ?, step_index = ? "
                        "WHERE user_phone = ?",
                        (datetime.now(), new_step, sender),
                    )
                else:
                    cursor.execute(
                        "UPDATE active_meditations SET step_index = ? WHERE user_phone = ?",
                        (new_step, sender),
                    )
                conn.commit()

                from meditation_scheduler import clean_script_body

                body = clean_script_body(
                    script.get(keys[new_step], "Continue at your own pace.")
                )
                hint = self._meditation_pacing_hint(meditation, new_step, keys)
                return f"{body}{hint}"

            return (
                "During meditation: **ready** (start) · **next** (next part) · "
                "**pause** · **resume** · **end** · **status**"
            )
        except sqlite3.Error as e:
            logger.error("Database error in handle_meditation_progress: %s", e)
            return "An error occurred. Please try again later."
        finally:
            conn.close()

    def daily_affirmation(self, args, sender):
        if self.affirmations:
            return random.choice(self.affirmations)
        else:
            return "Sorry, no affirmations available right now."

    def start_checkin_command(self, args, sender):
        from checkin_flow import start_checkin

        return start_checkin(sender)

    def help_command(self, args, sender):
        return """Mental Wellness Buddy Commands:
/start - Begin your wellness journey
/checkin - Guided wellness check-in (mood + topic)
/mood [1-10] [note] - Log mood (optional note)
/breathe [calm|relaxation|energize] - Breathing exercise
/meditate [quick|medium|long] - Guided meditation (ready → next → end)
/affirmation - Random affirmation
/vent - Share thoughts; replies use sentiment + suggested commands
/analyze - 7-day mood summary
/remind on|off|status - Daily check-in reminder (optional)
/cancel - Cancel current flow
/help - This list

Admins: /stats · /ping · /invite"""

    def vent_session(self, args, sender):
        from vent_flow import start_vent

        return start_vent(sender)

    def mood_analysis(self, args, sender):
        conn = connect()
        c = conn.cursor()
        c.execute('''SELECT AVG(intensity), COUNT(*) 
                    FROM mood_logs 
                    WHERE user_phone = ? 
                    AND timestamp >= date('now', '-7 days')''',
                  (sender,))
        avg_mood, log_count = c.fetchone()
        conn.close()

        if not avg_mood:
            return "No mood data available yet. Start logging with /mood!"

        return (f"Your 7-day mood analysis:\n"
                f"Average mood: {avg_mood:.1f}/10\n"
                f"Logs this week: {log_count}\n\n"
                "Keep tracking your moods to see patterns and growth! 📊")

    def is_admin(self, phone_number):
        return _digits_only(phone_number) in self.admin_numbers

    def admin_stats_command(self, args, sender):
        if not self.is_admin(sender):
            return "Access denied. Admin only."
        from admin_stats import fetch_bot_stats, format_stats_message

        return format_stats_message(fetch_bot_stats())

    def admin_ping_command(self, args, sender):
        if not self.is_admin(sender):
            return "Access denied. Admin only."
        from admin_stats import format_ping_message

        return format_ping_message()

    def admin_invite_command(self, args, sender):
        if not self.is_admin(sender):
            return "Access denied. Admin only."
        display = (os.environ.get("WHATSAPP_DISPLAY_NUMBER") or "").strip()
        if not display:
            return (
                "Set WHATSAPP_DISPLAY_NUMBER in Render (digits only, country code, no +).\n"
                "Example: 15551234567 for a US test number.\n"
                "Find it in Meta → WhatsApp → API Setup (business phone)."
            )
        from wa_me import build_wa_me_link

        link = build_wa_me_link(display, "Hi")
        return (
            "*Share this link* (friend must be added as Meta tester first):\n"
            f"{link}\n\n"
            "Steps:\n"
            "1. Meta Developer → WhatsApp → add their phone to tester list\n"
            "2. They open the link and tap Send\n"
            "3. They type /start\n\n"
            "See DEPLOY.md → Friends demo."
        )

    def remind_command(self, args, sender):
        from checkin_nudge_scheduler import (
            _nudge_hour,
            _nudge_window_minutes,
            get_reminder_status,
            nudges_enabled,
            set_daily_reminder,
        )

        sub = (args or "").strip().lower()
        tz_name = os.environ.get("TIMEZONE", "UTC")
        hour = _nudge_hour()
        window = _nudge_window_minutes()

        if sub in ("on", "enable", "yes"):
            set_daily_reminder(sender, True)
            if not nudges_enabled():
                return (
                    "Reminder saved. Note: server has ENABLE_DAILY_CHECKIN_NUDGES=false, "
                    "so pushes will not run until your host enables it."
                )
            return (
                f"Daily reminder is **ON**.\n"
                f"You'll get one message every morning around **{hour}:00** "
                f"({hour}:00–{hour}:{window - 1:02d} {tz_name}) until you send **/remind off**.\n"
                "First nudge: next time that window comes (not in the evening)."
            )
        if sub in ("off", "disable", "no"):
            set_daily_reminder(sender, False)
            return "Daily reminder is **OFF**. You won't get morning nudges anymore."
        status = get_reminder_status(sender)
        state = "ON" if status["enabled"] else "OFF"
        last = status["last_sent_date"] or "never"
        if status["enabled"]:
            return (
                f"Daily reminder: **{state}** (every ~{hour}:00 {tz_name} until /remind off).\n"
                f"Last sent: {last}."
            )
        return f"Daily reminder: **{state}**. Last sent: {last}. Send **/remind on** to start."

    def get_command_and_args(self, message):
        """Return (command, args) only for messages that start with /."""
        stripped = message.strip()
        if not stripped.startswith("/"):
            return "", ""
        parts = stripped.split(" ", 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        return command, args
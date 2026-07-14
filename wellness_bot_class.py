import json
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
import random

from db_paths import connect
from db_sql import execute, insert_user_ignore, is_db_error, upsert_active_meditation

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
        self._add_user_to_db(sender)
        from languages import t

        return t(sender, "welcome")

    def _add_user_to_db(self, phone_number):
        try:
            conn = connect()
            c = conn.cursor()
            insert_user_ignore(c, phone_number, datetime.now())
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error adding user to DB: {e}")

    def log_mood(self, args, sender):
        if not args.strip():
            from checkin_flow import start_checkin

            return start_checkin(sender)

        try:
            parts = args.split(' ', 1)
            intensity = int(parts[0])
            notes = parts[1] if len(parts) > 1 else ''

            if not 1 <= intensity <= 10:
                from languages import t

                return t(sender, "mood_invalid_rating")

            if notes:
                from sentiment_nlp import detect_crisis, handle_crisis

                if detect_crisis(notes):
                    return handle_crisis(sender, notes, source="mood", intensity=intensity)

            conn = connect()
            c = conn.cursor()
            execute(
                c,
                """INSERT INTO mood_logs (user_phone, mood, intensity, timestamp, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (sender, "mood_log", intensity, datetime.now(), notes),
            )
            conn.commit()
            conn.close()

            try:
                from llm_wellness import mood_log_reply

                personalized = mood_log_reply(sender, intensity, notes)
                if personalized:
                    return personalized
            except Exception as e:
                logger.error("Mood log LLM reply failed: %s", e)

            if intensity <= 4:
                return (
                    f"Logged {intensity}/10 — that's a heavy place to be. "
                    "Want to talk it through? /vent is a good space for that."
                )
            if intensity <= 6:
                return (
                    f"Logged {intensity}/10. Be gentle with yourself today. "
                    "/breathe or /vent might help if you want."
                )
            return (
                f"Logged {intensity}/10 — good to name that. "
                "Hope the rest of your day has room for more of this."
            )

        except ValueError:
            return "Use a number 1–10, then an optional note. Example: /mood 7 feeling okay"
        except Exception as e:
            logger.error(f"Error logging mood: {e}")
            return "Sorry, there was an error logging your mood. Please try again later."

    def breathing_exercise(self, args, sender):
        from languages import t

        if not args.strip():
            return t(sender, "breathe_choose")

        pattern_name = args.lower().split()[0]
        if pattern_name not in self.breathing_patterns:
            return t(sender, "breathe_not_found")
        pattern = self.breathing_patterns[pattern_name]
        cycle = pattern["inhale"] + pattern["hold"] + pattern["exhale"]
        total_sec = cycle * pattern["rounds"]
        duration = f"~{total_sec // 60} min" if total_sec >= 60 else f"~{total_sec}s"
        display_name = t(sender, f"breathe_name_{pattern_name}")

        return t(
            sender,
            "breathe_guide",
            name=display_name,
            duration=duration,
            inhale=str(pattern["inhale"]),
            hold=str(pattern["hold"]),
            exhale=str(pattern["exhale"]),
            rounds=str(pattern["rounds"]),
        )

    def clear_active_meditation(self, sender: str) -> None:
        try:
            conn = connect()
            c = conn.cursor()
            execute(c, "DELETE FROM active_meditations WHERE user_phone = ?", (sender,))
            conn.commit()
            conn.close()
        except Exception as e:
            if is_db_error(e):
                logger.error("Error clearing meditation: %s", e)

    @staticmethod
    def _meditation_script_keys(meditation: dict) -> list:
        intervals = meditation.get("intervals") or []
        if intervals:
            return [str(i) for i in sorted(intervals)]
        return sorted(meditation.get("script", {}).keys(), key=lambda k: int(k))

    def _meditation_pacing_hint(self, sender: str, meditation: dict, step_index: int, keys: list) -> str:
        from languages import t

        if step_index >= len(keys) - 1:
            return t(sender, "med_pacing_end")

        intervals = meditation.get("intervals") or []
        try:
            from meditation_scheduler import nudges_enabled

            if nudges_enabled() and step_index < len(keys) - 1 and len(intervals) > step_index + 1:
                gap = intervals[step_index + 1] - intervals[1]
                if gap > 0:
                    return t(sender, "med_pacing_auto", gap=str(gap))
        except ImportError:
            pass

        if step_index < len(intervals) - 1:
            gap = intervals[step_index + 1] - intervals[step_index]
            if gap > 0:
                return t(sender, "med_pacing_pause", gap=str(gap))
        return t(sender, "med_pacing_next")

    def _localize_script(self, sender: str, body: str) -> str:
        try:
            from llm_wellness import localize_wellness_content

            return localize_wellness_content(sender, body, kind="meditation")
        except Exception:
            return body

    def _prior_meditation_count(self, sender: str) -> int:
        try:
            conn = connect()
            c = conn.cursor()
            execute(
                c,
                "SELECT COUNT(*) FROM meditation_sessions WHERE user_phone = ?",
                (sender,),
            )
            count = int(c.fetchone()[0] or 0)
            conn.close()
            return count
        except Exception as e:
            if is_db_error(e):
                return 0
            raise

    def _post_exercise_line(self, sender: str, activity: str, fallback: str) -> str:
        try:
            from llm_wellness import post_session_reflection

            line = post_session_reflection(sender, activity)
            if line:
                return line
        except Exception:
            pass
        return fallback

    def meditation_guide(self, args, sender):
        from languages import t

        if not args.strip():
            options = [
                t(
                    sender,
                    "med_option_line",
                    med_key=key,
                    duration=str(value["duration"]),
                    parts=str(len(self._meditation_script_keys(value))),
                )
                for key, value in self.meditations.items()
            ]
            return t(sender, "meditation_choose") + "\n" + "\n".join(options)

        meditation_type = args.lower().split()[0]
        if meditation_type not in self.meditations:
            return t(sender, "med_invalid_type")

        selected = self.meditations[meditation_type]
        keys = self._meditation_script_keys(selected)
        returning = self._prior_meditation_count(sender) > 0

        conn = connect()
        c = conn.cursor()
        try:
            upsert_active_meditation(c, sender, meditation_type)
            execute(
                c,
                """INSERT INTO meditation_sessions (user_phone, duration, type, started_at)
                   VALUES (?, ?, ?, ?)""",
                (sender, selected["duration"], meditation_type, datetime.now()),
            )
            conn.commit()
        except Exception as e:
            if is_db_error(e):
                logger.error("Database error logging meditation session: %s", e)
                conn.rollback()
        finally:
            conn.close()

        if returning:
            return t(
                sender,
                "med_returning_intro",
                duration=str(selected["duration"]),
                type=meditation_type,
                parts=str(len(keys)),
            )

        intro_raw = selected["script"].get(keys[0], t(sender, "med_default_intro"))
        intro = self._localize_script(sender, intro_raw)
        return f"{intro}\n\n" + t(
            sender,
            "med_session_footer",
            duration=str(selected["duration"]),
            parts=str(len(keys)),
        )

    def handle_meditation_progress(self, message, sender):
        from languages import t

        conn = connect()
        cursor = conn.cursor()

        try:
            execute(
                cursor,
                """SELECT meditation_type, start_time, paused, step_index
                   FROM active_meditations WHERE user_phone = ?""",
                (sender,),
            )
            row = cursor.fetchone()

            if row is None:
                return t(sender, "med_not_started")

            meditation_type, start_time, paused, step_index = row
            step_index = step_index or 0
            meditation = self.meditations.get(meditation_type)
            if not meditation:
                execute(cursor, "DELETE FROM active_meditations WHERE user_phone = ?", (sender,))
                conn.commit()
                return t(sender, "med_type_error", type=meditation_type)

            keys = self._meditation_script_keys(meditation)
            script = meditation.get("script", {})
            msg = message.lower().strip()

            if msg == "status":
                paused_suffix = t(sender, "med_status_paused_suffix") if paused else ""
                return t(
                    sender,
                    "med_status",
                    type=meditation_type,
                    duration=str(meditation["duration"]),
                    part=str(step_index + 1),
                    total=str(len(keys)),
                    paused_suffix=paused_suffix,
                )

            if msg == "end":
                execute(cursor, "DELETE FROM active_meditations WHERE user_phone = ?", (sender,))
                conn.commit()
                closing = self._post_exercise_line(
                    sender,
                    f"a {meditation['duration']}-minute {meditation_type} meditation",
                    t(sender, "med_end_fallback"),
                )
                return f"{closing}\n\n{t(sender, 'med_end_followup')}"

            if msg == "pause":
                execute(
                    cursor,
                    "UPDATE active_meditations SET paused = 1 WHERE user_phone = ?",
                    (sender,),
                )
                conn.commit()
                return t(sender, "med_paused")

            if msg == "resume":
                execute(
                    cursor,
                    "UPDATE active_meditations SET paused = 0 WHERE user_phone = ?",
                    (sender,),
                )
                conn.commit()
                return t(sender, "med_resumed")

            if paused:
                return t(sender, "med_pause_blocked")

            if msg in ("ready", "next"):
                if msg == "ready" and step_index > 0:
                    return t(sender, "med_already_started")

                new_step = 1 if msg == "ready" else step_index + 1
                if new_step >= len(keys):
                    execute(
                        cursor,
                        "DELETE FROM active_meditations WHERE user_phone = ?",
                        (sender,),
                    )
                    conn.commit()
                    closing = self._post_exercise_line(
                        sender,
                        f"a {meditation['duration']}-minute {meditation_type} meditation",
                        self._localize_script(
                            sender, script.get(keys[-1], t(sender, "med_end_fallback"))
                        ),
                    )
                    return f"{closing}\n\n{t(sender, 'med_end_followup_alt')}"

                if msg == "ready" and not start_time:
                    execute(
                        cursor,
                        "UPDATE active_meditations SET start_time = ?, step_index = ? "
                        "WHERE user_phone = ?",
                        (datetime.now(), new_step, sender),
                    )
                else:
                    execute(
                        cursor,
                        "UPDATE active_meditations SET step_index = ? WHERE user_phone = ?",
                        (new_step, sender),
                    )
                conn.commit()

                from meditation_scheduler import clean_script_body

                body = clean_script_body(
                    script.get(keys[new_step], t(sender, "med_default_continue"))
                )
                body = self._localize_script(sender, body)
                hint = self._meditation_pacing_hint(sender, meditation, new_step, keys)
                return f"{body}{hint}"

            return t(sender, "med_help_during")
        except Exception as e:
            if is_db_error(e):
                logger.error("Database error in handle_meditation_progress: %s", e)
                return t(sender, "med_error")
            raise
        finally:
            conn.close()

    def daily_affirmation(self, args, sender):
        try:
            from llm_wellness import personalized_affirmation

            personalized = personalized_affirmation(sender)
            if personalized:
                return personalized
        except Exception as e:
            logger.error("Personalized affirmation failed: %s", e)

        if self.affirmations:
            return random.choice(self.affirmations)
        from languages import t

        return t(sender, "affirmation_empty")

    def weekly_summary_command(self, args, sender):
        try:
            from llm_wellness import weekly_summary_text

            return weekly_summary_text(sender)
        except Exception as e:
            logger.error("Weekly summary failed: %s", e)
            from languages import t

            return t(sender, "summary_error")

    def start_checkin_command(self, args, sender):
        from checkin_flow import start_checkin

        return start_checkin(sender)

    def help_command(self, args, sender):
        from languages import t

        return t(sender, "help")

    def language_command(self, args, sender):
        """Handled in bot_router with language picker UI."""
        from languages import t

        return t(sender, "language_pick")

    def vent_session(self, args, sender):
        from chat_flow import start_chat

        return start_chat(sender)

    def mood_analysis(self, args, sender):
        """Legacy alias — weekly summary includes trends now."""
        return self.weekly_summary_command(args, sender)

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
            VALID_MODES,
            _nudge_hour,
            _nudge_window_minutes,
            get_reminder_status,
            nudges_enabled,
            set_daily_reminder,
            set_reminder_mode,
        )

        parts = (args or "").strip().split(None, 1)
        sub = (parts[0] if parts else "").lower()
        rest = (parts[1] if len(parts) > 1 else "").strip().lower()
        tz_name = os.environ.get("TIMEZONE", "UTC")
        hour = _nudge_hour()
        window = _nudge_window_minutes()
        end_h = hour + (window - 1) // 60
        end_m = (window - 1) % 60

        if sub in ("on", "enable", "yes"):
            mode = rest if rest in VALID_MODES else "both"
            set_daily_reminder(sender, True, mode=mode)
            if not nudges_enabled():
                return (
                    "Reminder saved. Note: server has ENABLE_DAILY_CHECKIN_NUDGES=false, "
                    "so pushes will not run until your host enables it."
                )
            return (
                f"Morning companion is **ON** (mode: **{mode}**).\n"
                f"You'll get one message in roughly **{hour}:00–{end_h}:{end_m:02d} {tz_name}** "
                f"until **/remind off**.\n"
                "Modes: `/remind mode affirmation` · `checkin` · `both`\n"
                "Also try **/care on** for extra check-ins when things look rough.\n\n"
                "_Needs the bot host awake (e.g. UptimeRobot pinging /health) and "
                "that you've messaged within ~24h (WhatsApp rule)._"
            )
        if sub in ("off", "disable", "no"):
            set_daily_reminder(sender, False)
            return "Morning companion is **OFF**. Evening care pings are unchanged — use **/care off** for those."
        if sub == "mode" and rest in VALID_MODES:
            set_reminder_mode(sender, rest)
            status = get_reminder_status(sender)
            on = "ON" if status["enabled"] else "OFF"
            return (
                f"Morning mode set to **{rest}**. Reminder is currently **{on}**.\n"
                "Send **/remind on** if it is off."
            )
        if sub == "mode":
            return "Usage: `/remind mode affirmation` · `checkin` · `both`"

        status = get_reminder_status(sender)
        state = "ON" if status["enabled"] else "OFF"
        last = status["last_sent_date"] or "never"
        mode = status.get("mode") or "both"
        care = "ON" if status.get("care_enabled") else "OFF"
        if status["enabled"]:
            return (
                f"Morning companion: **{state}** · mode **{mode}** "
                f"(~{hour}:00–{end_h}:{end_m:02d} {tz_name}).\n"
                f"Care pings: **{care}**. Last morning send: {last}.\n"
                "`/remind off` · `/remind mode …` · `/care on|off`"
            )
        return (
            f"Morning companion: **{state}** (mode {mode}). Care pings: **{care}**. "
            f"Last morning send: {last}.\n"
            "Send **/remind on** to start · **/care on** for gentle low-mood check-ins."
        )

    def care_command(self, args, sender):
        from checkin_nudge_scheduler import (
            _care_hour,
            _care_min_days_between,
            care_pings_enabled,
            get_reminder_status,
            set_care_enabled,
        )

        sub = (args or "").strip().lower()
        tz_name = os.environ.get("TIMEZONE", "UTC")
        hour = _care_hour()

        if sub in ("on", "enable", "yes"):
            set_care_enabled(sender, True)
            if not care_pings_enabled():
                return (
                    "Care pings saved. Note: server has care pings disabled "
                    "(ENABLE_CARE_PINGS / ENABLE_DAILY_CHECKIN_NUDGES)."
                )
            return (
                f"Care pings are **ON**.\n"
                f"If mood trends look rough, I may gently check in around **{hour}:00 {tz_name}** "
                f"(at most about every {_care_min_days_between()} day(s)).\n"
                "Never a flood — and only while WhatsApp still allows free messages "
                "(you've messaged within ~24h). **/care off** anytime."
            )
        if sub in ("off", "disable", "no"):
            set_care_enabled(sender, False)
            return "Care pings are **OFF**."

        status = get_reminder_status(sender)
        state = "ON" if status.get("care_enabled") else "OFF"
        last = status.get("last_care_sent_date") or "never"
        return (
            f"Care pings: **{state}**. Last care send: {last}.\n"
            "Send **/care on** for gentle check-ins when things look rough · **/care off** to stop."
        )

    def get_command_and_args(self, message):
        """Return (command, args) only for messages that start with /."""
        stripped = message.strip()
        if not stripped.startswith("/"):
            return "", ""
        parts = stripped.split(" ", 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        return command, args
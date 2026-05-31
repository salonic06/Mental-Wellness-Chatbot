import json
import logging
from pathlib import Path

from checkin_flow import handle_checkin_message
from sentiment_nlp import detect_crisis, handle_crisis
from state_store import clear_user_state, get_user_state, set_user_state
from vent_flow import handle_vent_message
from wellness_bot_class import WellnessBot

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

_bot_instance = None
_command_map = None

VENT_SLASH_COMMANDS = frozenset(
    {
        "/breathe",
        "/affirmation",
        "/meditate",
        "/mood",
        "/help",
        "/done",
        "/cancel",
    }
)


def get_bot() -> WellnessBot:
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = WellnessBot()
    return _bot_instance


def load_commands() -> dict:
    global _command_map
    if _command_map is None:
        with open(BASE_DIR / "commands.json", "r", encoding="utf-8") as f:
            _command_map = json.load(f)
    return _command_map


def _dispatch_command(
    sender: str,
    command: str,
    args: str,
    session: dict,
    bot: WellnessBot,
    cmd_map: dict,
) -> str:
    """Run a slash command and update conversation state."""
    handler = getattr(bot, cmd_map[command])
    msg = handler(args, sender)

    if command == "/meditate":
        if args.strip():
            set_user_state(sender, "meditating", session.get("data", {}))
        else:
            set_user_state(sender, "meditation_choose", session.get("data", {}))
    elif command in ("/checkin", "/vent"):
        pass
    else:
        set_user_state(sender, "initial", session.get("data", {}))
    return msg


def _exit_meditation(bot: WellnessBot, sender: str) -> None:
    bot.clear_active_meditation(sender)
    clear_user_state(sender)


def process_message(sender: str, text: str) -> str:
    """Route inbound WhatsApp text to WellnessBot command handlers."""
    bot = get_bot()
    cmd_map = load_commands()
    stripped = text.strip()
    text_lower = stripped.lower()

    if stripped and detect_crisis(stripped):
        bot.clear_active_meditation(sender)
        clear_user_state(sender)
        return handle_crisis(sender, stripped, source="message")

    session = get_user_state(sender)
    current_state = session["state"]

    if current_state == "venting":
        command, args = bot.get_command_and_args(text_lower)
        if command in ("/done", "/cancel"):
            msg = handle_vent_message(sender, stripped)
            return msg or "Share what's on your mind, or type /done to finish."
        if command:
            if command in VENT_SLASH_COMMANDS and command in cmd_map:
                return _dispatch_command(sender, command, args, session, bot, cmd_map)
            allowed = ", ".join(sorted(c for c in VENT_SLASH_COMMANDS if c in cmd_map))
            return (
                f"That command isn't available during vent.\n"
                f"You can use: {allowed}\n"
                "Or share more text, or type /done to finish."
            )
        msg = handle_vent_message(sender, stripped)
        return msg or "Share what's on your mind, or type /done to finish."

    if current_state.startswith("checkin_"):
        msg = handle_checkin_message(sender, text.strip()) or ""
        return msg or "Type /checkin to start again."

    if current_state == "meditation_choose":
        command, args = bot.get_command_and_args(text_lower)
        if command == "/meditate" and args.strip():
            return _dispatch_command(sender, command, args, session, bot, cmd_map)
        if command in ("/cancel", "/done"):
            _exit_meditation(bot, sender)
            return "Cancelled. Type /help for commands."
        if command and command in cmd_map:
            bot.clear_active_meditation(sender)
            return _dispatch_command(sender, command, args, session, bot, cmd_map)
        return (
            "Choose a duration: /meditate quick, /meditate medium, or /meditate long.\n"
            "Or /cancel to stop."
        )

    if current_state == "meditating":
        command, args = bot.get_command_and_args(text_lower)
        if command:
            if command == "/meditate":
                return _dispatch_command(sender, command, args, session, bot, cmd_map)
            if command in ("/cancel", "/done"):
                _exit_meditation(bot, sender)
                return "Meditation ended. Type /help for commands."
            if command in cmd_map:
                bot.clear_active_meditation(sender)
                return _dispatch_command(sender, command, args, session, bot, cmd_map)
            return (
                "During meditation: ready, next, pause, resume, status, or end.\n"
                "Or /cancel to exit."
            )

        msg = bot.handle_meditation_progress(text_lower, sender)
        if msg.startswith("You haven't started"):
            set_user_state(sender, "meditation_choose", session.get("data", {}))
            return (
                f"{msg}\n\n"
                "Pick a duration: /meditate quick, /meditate medium, or /meditate long.\n"
                "Or /cancel to exit."
            )
        next_state = "initial" if text_lower == "end" else "meditating"
        set_user_state(sender, next_state, session.get("data", {}))
        return msg

    command, args = bot.get_command_and_args(text_lower)

    if command in ("/cancel", "cancel"):
        bot.clear_active_meditation(sender)
        clear_user_state(sender)
        return "Cancelled. Type /help for commands."

    if command in cmd_map:
        msg = _dispatch_command(sender, command, args, session, bot, cmd_map)
    elif command:
        msg = "Invalid command. Type /help for available commands."
        set_user_state(sender, "initial", session.get("data", {}))
    else:
        msg = "Use /start, /checkin, or /help to begin."
        set_user_state(sender, "initial", session.get("data", {}))
    return msg or "Type /help for available commands."

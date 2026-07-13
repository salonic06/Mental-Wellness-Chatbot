import json
import logging
from pathlib import Path

from bot_reply import BotReply
from checkin_flow import handle_checkin_message
from companion import handle_free_text
from interactive_maps import (
    BREATHE_BUTTONS,
    CHECKIN_CATEGORY_LIST,
    MAIN_MENU_LIST_SECTIONS,
    MEDITATION_BUTTONS,
    VENT_FOLLOWUP_BUTTONS,
    resolve_inbound_text,
)
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
) -> BotReply:
    handler = getattr(bot, cmd_map[command])
    msg = handler(args, sender)

    if command == "/meditate":
        if args.strip():
            set_user_state(sender, "meditating", session.get("data", {}))
            return BotReply(msg)
        set_user_state(sender, "meditation_choose", session.get("data", {}))
        return BotReply(msg, buttons=MEDITATION_BUTTONS)

    if command == "/breathe" and not args.strip():
        return BotReply(msg, buttons=BREATHE_BUTTONS)

    if command in ("/checkin", "/vent"):
        pass
    else:
        set_user_state(sender, "initial", session.get("data", {}))

    if command == "/start":
        return BotReply(
            msg,
            list_button_label="Open menu",
            list_sections=MAIN_MENU_LIST_SECTIONS,
        )

    if command == "/help":
        return BotReply(
            msg,
            list_button_label="Quick actions",
            list_sections=MAIN_MENU_LIST_SECTIONS,
        )

    return BotReply(msg)


def _exit_meditation(bot: WellnessBot, sender: str) -> None:
    bot.clear_active_meditation(sender)
    clear_user_state(sender)


def _meditate_from_interactive(stripped: str) -> tuple:
    """Return (/meditate, args) if id is a meditation length button."""
    mapped = resolve_inbound_text(stripped)
    if mapped.startswith("/meditate "):
        parts = mapped.split(maxsplit=1)
        return "/meditate", parts[1] if len(parts) > 1 else ""
    return "", ""


def _checkin_reply(sender: str, text: str) -> BotReply:
    msg = handle_checkin_message(sender, text.strip()) or "Type /checkin to start again."
    if get_user_state(sender)["state"] == "checkin_category":
        return BotReply(
            msg,
            list_button_label="Pick topic",
            list_sections=CHECKIN_CATEGORY_LIST,
        )
    return BotReply(msg)


def process_message(sender: str, raw_text: str) -> BotReply:
    """Route inbound WhatsApp text or interactive id to handlers."""
    bot = get_bot()
    cmd_map = load_commands()
    stripped = resolve_inbound_text(raw_text.strip())
    text_lower = stripped.lower()

    if stripped and detect_crisis(stripped):
        bot.clear_active_meditation(sender)
        clear_user_state(sender)
        return BotReply(handle_crisis(sender, stripped, source="message"))

    session = get_user_state(sender)
    current_state = session["state"]

    if current_state == "venting":
        if stripped == "vent_done":
            return BotReply(
                handle_vent_message(sender, "/done") or "Vent ended. Type /help anytime."
            )
        command, args = bot.get_command_and_args(text_lower)
        if command in ("/done", "/cancel"):
            return BotReply(handle_vent_message(sender, raw_text.strip()) or "")
        # Common commands break out of vent and run normally (/start was confusing in REPL).
        if command in ("/start", "/help", "/checkin", "/summary", "/analyze", "/mood"):
            clear_user_state(sender)
            if command in cmd_map:
                return _dispatch_command(sender, command, args, session, bot, cmd_map)
        if command and command in VENT_SLASH_COMMANDS and command in cmd_map:
            return _dispatch_command(sender, command, args, session, bot, cmd_map)
        if command:
            return BotReply(
                "Use the buttons below, type /done to finish venting, or keep sharing."
            )
        msg = handle_vent_message(sender, stripped) or "Share what's on your mind."
        if msg.startswith("Thank you for sharing") or msg.startswith("Vent session ended"):
            return BotReply(msg)
        return BotReply(msg, buttons=VENT_FOLLOWUP_BUTTONS)

    if current_state.startswith("checkin_"):
        return _checkin_reply(sender, stripped)

    if current_state == "meditation_choose":
        med_cmd, med_args = _meditate_from_interactive(stripped)
        if med_cmd:
            return _dispatch_command(sender, med_cmd, med_args, session, bot, cmd_map)
        command, args = bot.get_command_and_args(text_lower)
        if command == "/meditate" and args.strip():
            return _dispatch_command(sender, command, args, session, bot, cmd_map)
        if command in ("/cancel", "/done") or stripped == "cmd_cancel":
            _exit_meditation(bot, sender)
            return BotReply("Cancelled. Type /help for commands.")
        if command and command in cmd_map:
            bot.clear_active_meditation(sender)
            return _dispatch_command(sender, command, args, session, bot, cmd_map)
        return BotReply("Choose a meditation length:", buttons=MEDITATION_BUTTONS)

    if current_state == "meditating":
        command, args = bot.get_command_and_args(text_lower)
        if command:
            if command == "/meditate":
                return _dispatch_command(sender, command, args, session, bot, cmd_map)
            if command in ("/cancel", "/done") or stripped == "cmd_cancel":
                _exit_meditation(bot, sender)
                return BotReply("Meditation ended. Type /help for commands.")
            if command in cmd_map:
                bot.clear_active_meditation(sender)
                return _dispatch_command(sender, command, args, session, bot, cmd_map)
            return BotReply(
                "During meditation: ready, next, pause, resume, status, or end.\n"
                "Or /cancel to exit."
            )

        msg = bot.handle_meditation_progress(text_lower, sender)
        if msg.startswith("You haven't started"):
            set_user_state(sender, "meditation_choose", session.get("data", {}))
            return BotReply(f"{msg}\n\nChoose a length:", buttons=MEDITATION_BUTTONS)
        next_state = "initial" if text_lower == "end" else "meditating"
        set_user_state(sender, next_state, session.get("data", {}))
        return BotReply(msg)

    # Interactive quick actions from initial state
    if stripped.startswith("cmd_") or stripped.startswith("med_") or stripped.startswith("breathe_"):
        mapped = resolve_inbound_text(stripped)
        command, args = bot.get_command_and_args(mapped.lower())
        if command in cmd_map:
            return _dispatch_command(sender, command, args, session, bot, cmd_map)

    command, args = bot.get_command_and_args(text_lower)

    if command in ("/cancel", "cancel") or stripped == "cmd_cancel":
        bot.clear_active_meditation(sender)
        clear_user_state(sender)
        return BotReply("Cancelled. Type /help for commands.")

    if command in cmd_map:
        reply = _dispatch_command(sender, command, args, session, bot, cmd_map)
    elif command:
        reply = BotReply("I didn't catch that command — open the menu or type /help.")
        set_user_state(sender, "initial", session.get("data", {}))
    else:
        reply = handle_free_text(sender, stripped)
        set_user_state(sender, "initial", session.get("data", {}))

    return reply if reply.text else BotReply("Type /help for commands.")

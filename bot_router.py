import json
import logging
from pathlib import Path

from bot_reply import BotReply
from checkin_flow import handle_checkin_message
from command_normalize import is_done_signal, normalize_inbound
from companion import handle_free_text
from interactive_maps import (
    BREATHE_BUTTONS,
    CHAT_FOLLOWUP_BUTTONS,
    CHECKIN_CATEGORY_LIST,
    MAIN_MENU_LIST_SECTIONS,
    MEDITATION_BUTTONS,
)
from patterns import CHAT_STATES
from sentiment_nlp import detect_crisis, handle_crisis
from session_offers import try_fulfill_offer
from state_store import clear_user_state, get_user_state, set_user_state
from chat_flow import handle_chat_message, is_chatting
from wellness_bot_class import WellnessBot

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

_bot_instance = None
_command_map = None

CHAT_SLASH_COMMANDS = frozenset(
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
    if command == "/analyze":
        command = "/summary"
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
    elif command == "/mood" and not args.strip():
        pass
    else:
        set_user_state(sender, "initial", session.get("data", {}))

    if command == "/start":
        return BotReply(
            msg,
            list_button_label="Wellness menu",
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
    mapped = normalize_inbound(stripped)
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


def _handle_offer_dispatch(sender: str, offer_msg: str, session: dict, bot: WellnessBot, cmd_map: dict) -> BotReply:
    offer_cmd = offer_msg.split(":", 1)[1].strip()
    parts = offer_cmd.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    if command not in cmd_map:
        return BotReply("Let's try that again — open the menu or type /help.")
    clear_user_state(sender)
    return _dispatch_command(sender, command, args, session, bot, cmd_map)


def process_message(sender: str, raw_text: str) -> BotReply:
    """Route inbound WhatsApp text or interactive id to handlers."""
    bot = get_bot()
    cmd_map = load_commands()
    stripped = normalize_inbound(raw_text.strip())
    text_lower = stripped.lower()

    if stripped and detect_crisis(stripped):
        bot.clear_active_meditation(sender)
        clear_user_state(sender)
        return BotReply(handle_crisis(sender, stripped, source="message"))

    session = get_user_state(sender)
    current_state = session["state"]

    def _dispatch(cmd: str, args: str = "") -> BotReply:
        if cmd == "/analyze":
            cmd = "/summary"
        return _dispatch_command(sender, cmd, args, session, bot, cmd_map)

    # Pause chat button /done — works in or out of chat mode
    if is_done_signal(raw_text, stripped):
        if is_chatting(sender) or current_state in CHAT_STATES:
            msg = handle_chat_message(sender, "/done") or "Chat paused."
            return BotReply(msg)
        return BotReply("No open chat to pause — just tell me how you're doing.")

    # Accept pending offers ("sure", "yes", …) before anything else
    offer_reply = try_fulfill_offer(sender, stripped, _dispatch)
    if offer_reply:
        return offer_reply

    if is_chatting(sender) or current_state in CHAT_STATES:
        command, args = bot.get_command_and_args(text_lower)
        if command in ("/done", "/cancel"):
            return BotReply(handle_chat_message(sender, stripped) or "")
        if command in ("/start", "/help", "/checkin", "/summary", "/analyze", "/mood"):
            clear_user_state(sender)
            return _dispatch(command, args)
        if command and command in CHAT_SLASH_COMMANDS and command in cmd_map:
            clear_user_state(sender)
            return _dispatch(command, args)
        if command and command in cmd_map:
            return BotReply("Keep sharing, or /done to pause this chat.")
        if command:
            return BotReply("Keep sharing, or /done to pause this chat.")

        msg = handle_chat_message(sender, stripped) or "I'm listening."
        if msg.startswith("__OFFER__:"):
            return _handle_offer_dispatch(sender, msg, session, bot, cmd_map)
        if msg.startswith("I'm glad you shared") or msg.startswith("Chat paused"):
            return BotReply(msg)
        return BotReply(msg, buttons=CHAT_FOLLOWUP_BUTTONS)

    if current_state.startswith("checkin_"):
        return _checkin_reply(sender, stripped)

    if current_state == "meditation_choose":
        med_cmd, med_args = _meditate_from_interactive(stripped)
        if med_cmd:
            return _dispatch(med_cmd, med_args)
        command, args = bot.get_command_and_args(text_lower)
        if command == "/meditate" and args.strip():
            return _dispatch(command, args)
        if command in ("/cancel", "/done") or stripped == "cmd_cancel":
            _exit_meditation(bot, sender)
            return BotReply("Cancelled. Type /help for commands.")
        if command and command in cmd_map:
            bot.clear_active_meditation(sender)
            return _dispatch(command, args)
        return BotReply("Choose a meditation length:", buttons=MEDITATION_BUTTONS)

    if current_state == "meditating":
        command, args = bot.get_command_and_args(text_lower)
        if command:
            if command == "/meditate":
                return _dispatch(command, args)
            if command in ("/cancel", "/done") or stripped == "cmd_cancel":
                _exit_meditation(bot, sender)
                return BotReply("Meditation ended. Type /help for commands.")
            if command in cmd_map:
                bot.clear_active_meditation(sender)
                return _dispatch(command, args)
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

    if stripped.startswith("cmd_") or stripped.startswith("med_") or stripped.startswith("breathe_"):
        mapped = normalize_inbound(stripped)
        command, args = bot.get_command_and_args(mapped.lower())
        if command in cmd_map:
            return _dispatch(command, args)

    command, args = bot.get_command_and_args(text_lower)

    if command in ("/cancel", "cancel") or stripped == "cmd_cancel":
        bot.clear_active_meditation(sender)
        clear_user_state(sender)
        return BotReply("Cancelled. Type /help for commands.")

    if command in cmd_map:
        reply = _dispatch(command, args)
    elif command:
        reply = BotReply("I didn't catch that — try /help or open the menu.")
        set_user_state(sender, "initial", session.get("data", {}))
    else:
        reply = handle_free_text(sender, stripped)
        if not is_chatting(sender):
            set_user_state(sender, "initial", session.get("data", {}))

    return reply if reply.text else BotReply("Type /help for commands.")

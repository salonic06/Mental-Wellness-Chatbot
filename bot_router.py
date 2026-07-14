import json
import logging
from pathlib import Path

from bot_reply import BotReply
from checkin_flow import handle_checkin_message
from command_normalize import is_done_signal, normalize_inbound
from companion import handle_free_text
from languages import (
    language_list_sections,
    language_picker_reply,
    language_set_message,
    main_menu_sections,
    meditation_buttons,
    breathe_buttons,
    chat_followup_buttons,
    checkin_category_list,
    parse_language_choice,
    set_user_language,
    t,
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
        return BotReply(msg, buttons=meditation_buttons(sender))

    if command == "/breathe" and not args.strip():
        return BotReply(msg, buttons=breathe_buttons(sender))

    if command in ("/checkin", "/vent"):
        pass
    elif command == "/mood" and not args.strip():
        pass
    else:
        set_user_state(sender, "initial", session.get("data", {}))

    if command == "/start":
        return BotReply(
            msg,
            list_button_label=t(sender, "menu_label"),
            list_sections=main_menu_sections(sender),
        )

    if command == "/help":
        return BotReply(
            msg,
            list_button_label=t(sender, "help_menu_label"),
            list_sections=main_menu_sections(sender),
        )

    if command == "/language":
        if args.strip():
            parsed = parse_language_choice(args.strip())
            if parsed:
                return _apply_language_choice(sender, f"lang_{parsed}")
        set_user_state(sender, "language_choose", session.get("data", {}))
        return language_picker_reply(sender)

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


def _apply_language_choice(sender: str, choice: str) -> BotReply:
    lang = parse_language_choice(choice) or "en"
    set_user_language(sender, lang)
    clear_user_state(sender)
    bot = get_bot()
    msg = bot.start_command("", sender)
    return BotReply(
        language_set_message(lang) + "\n\n" + msg,
        list_button_label=t(sender, "menu_label"),
        list_sections=main_menu_sections(sender),
    )


def _checkin_reply(sender: str, text: str) -> BotReply:
    msg = handle_checkin_message(sender, text.strip()) or "Type /checkin to start again."
    if get_user_state(sender)["state"] == "checkin_category":
        return BotReply(
            msg,
            list_button_label=t(sender, "checkin_topic_label"),
            list_sections=checkin_category_list(sender),
        )
    return BotReply(msg)


def _handle_offer_dispatch(sender: str, offer_msg: str, session: dict, bot: WellnessBot, cmd_map: dict) -> BotReply:
    offer_cmd = offer_msg.split(":", 1)[1].strip()
    parts = offer_cmd.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    if command not in cmd_map:
        return BotReply(t(sender, "router_try_again"))
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

    if stripped.startswith("lang_"):
        parsed = parse_language_choice(stripped)
        if parsed:
            return _apply_language_choice(sender, stripped)

    if current_state == "language_choose":
        parsed = parse_language_choice(stripped)
        if parsed:
            return _apply_language_choice(sender, f"lang_{parsed}")
        return BotReply(t(sender, "language_invalid"), list_button_label=t(sender, "lang_list_btn"), list_sections=language_list_sections(sender))

    def _dispatch(cmd: str, args: str = "") -> BotReply:
        if cmd == "/analyze":
            cmd = "/summary"
        return _dispatch_command(sender, cmd, args, session, bot, cmd_map)

    # Pause chat button /done — works in chat mode; during meditation ends session
    if is_done_signal(raw_text, stripped):
        if current_state == "meditating":
            msg = bot.handle_meditation_progress("end", sender)
            set_user_state(sender, "initial", session.get("data", {}))
            return BotReply(msg)
        if is_chatting(sender) or current_state in CHAT_STATES:
            msg = handle_chat_message(sender, "/done") or t(sender, "router_chat_paused")
            return BotReply(msg)
        return BotReply(t(sender, "router_no_chat_pause"))

    # Accept pending offers ("sure", "yes", …) before anything else
    offer_reply = try_fulfill_offer(sender, stripped, _dispatch)
    if offer_reply:
        return offer_reply

    if is_chatting(sender) or current_state in CHAT_STATES:
        command, args = bot.get_command_and_args(text_lower)
        if command in ("/done", "/cancel"):
            return BotReply(handle_chat_message(sender, stripped) or "")
        if command == "/vent":
            # Already in chat — never dump the robotic "Keep sharing" shell.
            from llm_wellness import chat_already_open_reply

            ack = chat_already_open_reply(sender) or t(sender, "chat_keep_going")
            return BotReply(ack, buttons=chat_followup_buttons(sender))
        if command in ("/start", "/help", "/checkin", "/summary", "/analyze", "/mood", "/language"):
            clear_user_state(sender)
            return _dispatch(command, args)
        if command and command in CHAT_SLASH_COMMANDS and command in cmd_map:
            clear_user_state(sender)
            return _dispatch(command, args)
        if command and command in cmd_map:
            return BotReply(t(sender, "router_keep_sharing"))
        if command:
            return BotReply(t(sender, "router_keep_sharing"))

        msg = handle_chat_message(sender, stripped) or t(sender, "chat_keep_going")
        if msg.startswith("__OFFER__:"):
            return _handle_offer_dispatch(sender, msg, session, bot, cmd_map)
        if not is_chatting(sender):
            return BotReply(msg)
        return BotReply(msg, buttons=chat_followup_buttons(sender))

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
            return BotReply(t(sender, "router_cancelled"))
        if command and command in cmd_map:
            bot.clear_active_meditation(sender)
            return _dispatch(command, args)
        return BotReply(t(sender, "meditation_choose"), buttons=meditation_buttons(sender))

    if current_state == "meditating":
        command, args = bot.get_command_and_args(text_lower)
        if command:
            if command == "/meditate":
                return _dispatch(command, args)
            if command in ("/cancel", "/done") or stripped == "cmd_cancel":
                _exit_meditation(bot, sender)
                return BotReply(t(sender, "router_meditation_ended"))
            if command in cmd_map:
                bot.clear_active_meditation(sender)
                return _dispatch(command, args)
            return BotReply(t(sender, "router_meditation_during_help"))

        msg = bot.handle_meditation_progress(text_lower, sender)
        if msg == t(sender, "med_not_started"):
            set_user_state(sender, "meditation_choose", session.get("data", {}))
            return BotReply(
                f"{msg}\n\n{t(sender, 'meditation_choose')}",
                buttons=meditation_buttons(sender),
            )
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
        return BotReply(t(sender, "router_cancelled"))

    if command in cmd_map:
        reply = _dispatch(command, args)
    elif command:
        reply = BotReply(t(sender, "router_didnt_catch"))
        set_user_state(sender, "initial", session.get("data", {}))
    else:
        reply = handle_free_text(sender, stripped)
        if not is_chatting(sender):
            set_user_state(sender, "initial", session.get("data", {}))

    return reply if reply.text else BotReply(t(sender, "router_help_fallback"))

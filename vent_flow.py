"""Backward-compatible re-exports — chat mode is the primary implementation."""

from chat_flow import (  # noqa: F401
    enter_chat,
    handle_chat_message,
    handle_vent_message,
    is_chatting,
    start_chat,
    start_vent,
)

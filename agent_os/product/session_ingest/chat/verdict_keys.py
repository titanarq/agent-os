"""The key of a verdict the chat gave, by which `feedback.jsonl` says whose it is and that it was written."""

from __future__ import annotations

CHAT_VERDICT_PREFIX = "chat-verdict."


def chat_verdict_key(session_id: str, item_id: str) -> str:
    return f"{CHAT_VERDICT_PREFIX}{session_id}.{item_id}"


def is_chat_verdict_key(key: object) -> bool:
    return isinstance(key, str) and key.startswith(CHAT_VERDICT_PREFIX)


def belongs_to_session(key: str, session_id: str) -> bool:
    return key.startswith(f"{CHAT_VERDICT_PREFIX}{session_id}.")

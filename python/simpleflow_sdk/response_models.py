from __future__ import annotations

from typing import TypedDict


class ChatSession(TypedDict, total=False):
    chat_id: str
    status: str
    agent_id: str
    user_id: str
    metadata: dict[str, object]

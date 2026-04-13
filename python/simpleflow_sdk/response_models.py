from __future__ import annotations

from typing import TypedDict


class ChatSession(TypedDict, total=False):
    chat_id: str
    status: str
    agent_id: str
    user_id: str
    metadata: dict[str, object]


class ChatMessage(TypedDict, total=False):
    message_id: str
    chat_id: str
    agent_id: str
    user_id: str
    role: str
    content: dict[str, object]
    telemetry_data: dict[str, object]


class ChatSessionsResponse(TypedDict, total=False):
    sessions: list[ChatSession]
    page: int
    limit: int
    has_more: bool


class ChatMessagesResponse(TypedDict, total=False):
    messages: list[ChatMessage]

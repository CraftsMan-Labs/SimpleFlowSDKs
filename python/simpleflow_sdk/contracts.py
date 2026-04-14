from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ChatMessageWrite:
    agent_id: str
    user_id: str
    chat_id: str
    message_id: str
    role: str
    content: Any = None
    telemetry_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    idempotency_key: str | None = None


@dataclass(slots=True)
class ChatHistoryMessage:
    agent_id: str
    chat_id: str
    message_id: str
    user_id: str
    role: str | None = None
    content: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

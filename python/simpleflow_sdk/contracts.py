from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RuntimeEvent:
    agent_id: str
    event_type: str | None = None
    type: str | None = None
    run_id: str | None = None
    conversation_id: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    sampled: bool | None = None
    organization_id: str | None = None
    user_id: str | None = None
    timestamp_ms: int | None = None
    idempotency_key: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class ChatMessageWrite:
    agent_id: str
    organization_id: str
    run_id: str
    role: str
    chat_id: str | None = None
    message_id: str | None = None
    direction: str | None = None
    content: Any = None
    metadata: dict[str, Any] | None = None
    idempotency_key: str | None = None
    created_at_ms: int | None = None


@dataclass(slots=True)
class ChatHistoryMessage:
    agent_id: str
    chat_id: str
    message_id: str
    user_id: str
    role: str | None = None
    content: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

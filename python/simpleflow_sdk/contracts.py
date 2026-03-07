from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class InvokeTrace:
    trace_id: str
    span_id: str
    tenant_id: str


@dataclass(slots=True)
class RuntimeEvent:
    type: str
    agent_id: str
    agent_version: str
    run_id: str
    organization_id: str | None = None
    user_id: str | None = None
    timestamp_ms: int | None = None
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class ChatMessageWrite:
    agent_id: str
    organization_id: str
    run_id: str
    role: str
    content: str
    metadata: dict[str, Any] | None = None
    created_at_ms: int | None = None


@dataclass(slots=True)
class QueueContract:
    queue_name: str
    message_id: str
    idempotency_key: str
    retry_attempt: int
    max_retry_attempt: int
    payload: dict[str, Any]

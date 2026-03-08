from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class InvokeTrace:
    trace_id: str
    span_id: str
    tenant_id: str


@dataclass(slots=True)
class WorkflowTraceTenant:
    conversation_id: str | None = None
    request_id: str | None = None
    run_id: str | None = None
    agent_id: str | None = None


@dataclass(slots=True)
class RuntimeRegistration:
    runtime_id: str
    runtime_version: str | None = None
    capabilities: list[str] | None = None
    metadata: dict[str, str] | None = None


@dataclass(slots=True)
class RuntimeEvent:
    type: str
    agent_id: str
    agent_version: str | None = None
    run_id: str | None = None
    conversation_id: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    sampled: bool | None = None
    organization_id: str | None = None
    user_id: str | None = None
    timestamp_ms: int | None = None
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class TelemetrySpan:
    name: str
    start_time_ms: int
    end_time_ms: int
    kind: str | None = None
    attributes: dict[str, Any] | None = None
    status: str | None = None
    status_detail: str | None = None


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

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
    organization_id: str | None = None


@dataclass(slots=True)
class RuntimeRegistration:
    agent_id: str | None = None
    agent_version: str | None = None
    execution_mode: str | None = None
    endpoint_url: str | None = None
    auth_mode: str | None = None
    capabilities: list[str] | None = None
    metadata: dict[str, str] | None = None
    runtime_id: str | None = None
    runtime_version: str | None = None


@dataclass(slots=True)
class RuntimeEvent:
    agent_id: str
    event_type: str | None = None
    type: str | None = None
    agent_version: str | None = None
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
    chat_id: str | None = None
    message_id: str | None = None
    direction: str | None = None
    content: Any = None
    metadata: dict[str, Any] | None = None
    idempotency_key: str | None = None
    created_at_ms: int | None = None


@dataclass(slots=True)
class QueueContract:
    queue_name: str
    message_id: str
    idempotency_key: str
    retry_attempt: int
    max_retry_attempt: int
    agent_id: str | None = None
    organization_id: str | None = None
    run_id: str | None = None
    contract_name: str | None = None
    contract_version: str | None = None
    schema: dict[str, Any] | None = None
    transport: dict[str, Any] | None = None
    status: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class ChatHistoryMessage:
    agent_id: str
    chat_id: str
    message_id: str
    user_id: str
    role: str | None = None
    content: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

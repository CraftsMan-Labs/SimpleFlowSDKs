from __future__ import annotations

from typing import Any, Literal, TypedDict


class UsageSummary(TypedDict):
    prompt_tokens: int | float | None
    completion_tokens: int | float | None
    total_tokens: int | float | None
    reasoning_tokens: int | float | None
    ttft_ms: int | float | None
    total_elapsed_ms: int | float | None
    tokens_per_second: int | float | None
    token_metrics_available: bool
    token_metrics_source: str | None
    llm_nodes_without_usage: list[str]


class ModelUsageRow(TypedDict):
    model: str
    request_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    reasoning_tokens: int
    elapsed_ms: int


class ToolUsageRow(TypedDict):
    tool: str
    started_count: int
    completed_count: int
    error_count: int


class TelemetryIdentity(TypedDict):
    organization_id: str
    agent_id: str
    user_id: str


class TelemetryTrace(TypedDict):
    trace_id: str
    span_id: str
    tenant_id: str
    conversation_id: str
    request_id: str
    run_id: str
    sampled: bool


class TelemetryWorkflow(TypedDict):
    workflow_id: str
    terminal_node: str
    status: str
    total_elapsed_ms: int | float | None
    ttft_ms: int | float | None


class TelemetryEnvelopeV1(TypedDict, total=False):
    schema_version: Literal["telemetry-envelope.v1"]
    identity: TelemetryIdentity
    trace: TelemetryTrace
    workflow: TelemetryWorkflow
    usage: UsageSummary
    model_usage: list[ModelUsageRow]
    tool_usage: list[ToolUsageRow]
    event_counts: dict[str, int]
    nerdstats: dict[str, Any]
    raw: dict[str, Any]


class RuntimeActivationResult(TypedDict, total=False):
    status: Literal["active"]
    registration: dict[str, Any]
    registration_id: str
    validation: dict[str, Any]
    created: bool
    validated: bool
    activated: bool


class InvokeResult(TypedDict, total=False):
    schema_version: str
    run_id: str
    status: str
    output: dict[str, Any]
    error: dict[str, Any]
    metrics: dict[str, Any]


class ChatSession(TypedDict, total=False):
    chat_id: str
    status: str
    agent_id: str
    user_id: str
    metadata: dict[str, Any]

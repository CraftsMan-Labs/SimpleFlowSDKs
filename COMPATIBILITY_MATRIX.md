# Compatibility Matrix

This matrix tracks tested compatibility between SimpleAgents, SimpleFlow SDKs, and the SimpleFlow API contract.

## Contract Baseline

- Runtime events endpoint: `POST /v1/runtime/events`
- Control-plane runtime endpoints:
  - `POST /v1/runtime/registrations`
  - `POST /v1/runtime/invoke`
- Chat history endpoints:
  - `GET /v1/chat/history/messages`
  - `POST /v1/chat/history/messages`
  - `PATCH /v1/chat/history/messages/{message_id}`
- Required correlation envelope fields:
  - `agent_id`, `run_id`, `trace_id`, `request_id`, `conversation_id`, `sampled`

## Matrix

| SimpleAgents | SimpleFlowSDKs | SimpleFlow API Contract | Status | Notes |
| --- | --- | --- | --- | --- |
| `feat/telemetry-sample-rate-enforcement` and later | `main` (this repository, current) | `v1 runtime envelope` | ✅ validated | Deterministic trace-id-based sampling and `metadata.telemetry.sampled` are mapped by `write_event_from_workflow_result(...)`. |

## Validation Notes

- Go SDK tests cover workflow-result event mapping and telemetry bridge event emission.
- Python SDK tests cover workflow-result event mapping and deterministic sampling helper behavior.
- Go and Python SDK tests cover chat history list APIs.
- Both SDKs support telemetry mode routing:
  - `simpleflow`: emits runtime telemetry span events.
  - `otlp`: forwards spans to the caller-provided OTLP sink.

## Versioning Guidance

- If SimpleAgents changes workflow result metadata paths, bump SDK minor version and update mapping notes.
- If SimpleFlow runtime event envelope fields change incompatibly, bump SDK major version and update this matrix in the same change.

# SDK Integration Common Guide

This page defines the shared integration model used by Node, Python, and Go SDK guides.

## Auth model

- Machine auth (runtime connect + runtime writes): use `SIMPLEFLOW_API_TOKEN`, or use `MACHINE_CLIENT_ID` + `MACHINE_CLIENT_SECRET` and exchange via `/v1/oauth/token`.
- User auth (runtime invoke/chat history): use user bearer token.
- Chat entrypoint (`/api/v1/chat`): accepts API key (`agk_*`) or user bearer. `agent_id` is required.

## Shared env variables

Base:

- `SIMPLEFLOW_BASE_URL`

Machine auth:

- `SIMPLEFLOW_API_TOKEN`
- or `MACHINE_CLIENT_ID` + `MACHINE_CLIENT_SECRET`

Runtime identity:

- `SIMPLEFLOW_AGENT_ID`
- `SIMPLEFLOW_AGENT_VERSION`
- `SIMPLEFLOW_RUNTIME_ID`
- `SIMPLEFLOW_ORGANIZATION_ID`
- `RUNTIME_ENDPOINT_URL`

User-scoped APIs:

- `SIMPLEFLOW_USER_BEARER`

Workflow bridge:

- `WORKFLOW_PATH`

## Shared integration sequence

1. Create SDK client with `SIMPLEFLOW_BASE_URL` and machine auth.
2. Register runtime (`/v1/runtime/connect` or `/v1/runtime/registrations` depending on deployment).
3. Execute workflow.
4. Emit canonical telemetry via `writeEventFromWorkflowResult(...)`.
5. Optionally emit span telemetry with `withTelemetry(...).emitSpan(...)`.
6. Use chat history APIs with user bearer token when needed.

## Language-specific guides

- Node: [Node SDK Integration](/sdk-node-integration)
- Python: [Python SDK Integration](/sdk-python-integration)
- Go: [Go SDK Integration](/sdk-go-integration)

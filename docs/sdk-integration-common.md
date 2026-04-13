# SDK Integration Common Guide

This page defines the shared integration model used by Node, Python, and Go SDK guides.

## Auth model

- Machine auth (runtime connect + runtime writes): use `SIMPLEFLOW_API_TOKEN`, or use `MACHINE_CLIENT_ID` + `MACHINE_CLIENT_SECRET` and exchange via `/v1/oauth/token`.
- User auth (runtime invoke/chat history): use user bearer token.
- Chat entrypoint (`/api/v1/chat`): accepts API key (`agk_*`) or user bearer. `agent_id` is required.

## User session and authorization (remote agents)

Access tokens are opaque to permission logic: **org roles** (`member`, `admin`, `super_admin`) are **not** embedded in self-hosted JWT claims. Resolve the canonical user and roles with **`GET /v1/me`** using the same bearer token the browser or client sends.

SDK helpers (Python / Node):

- **`fetch_current_user` / `fetchCurrentUser`** — calls `GET /v1/me`; returns `user_id`, `organization_id`, `roles`, `email`, `full_name`.
- **`can_read_chat_user_scope` / `canReadChatUserScope`** — pure helper aligned with control-plane chat read rules: **`member`** may only use chat APIs for **`user_id` equal to their own** `user_id` from `/v1/me`; **`admin`** / **`super_admin`** may read other users’ chat data; an **empty** chat `user_id` (org-wide listing) is allowed only for **`admin`** / **`super_admin`**.
- **`fetch_agent` / `fetchAgent`** — `GET /api/v1/agents/{agent_id}`; **200** means the caller has **read** access to that agent; **403** means no read access (agent RBAC is not represented in the JWT).
- **`authorize_runtime_chat_read` / `authorizeChatRead`** — runs `/v1/me`, enforces chat scope for a target chat `user_id`, then fetches the agent; use before `listChatSessions` / `listChatMessages` when building a remote backend.

Do **not** use JWT `sub` as `user_id` for chat APIs on self-hosted auth: use **`user_id` from `/v1/me`** (or the login response) so it matches the control-plane user row.

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

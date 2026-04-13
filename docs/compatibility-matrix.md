# Compatibility Matrix

This matrix tracks tested compatibility between SimpleAgents, SimpleFlow SDKs, and the SimpleFlow API contract.

## Contract Baseline

- Chat write endpoint: `POST /v1/chat/sessions`
- Control-plane runtime endpoints:
  - `POST /v1/runtime/connect`
  - `POST /v1/runtime/invoke`
- Chat session endpoints:
  - `GET /v1/chat/sessions`
  - `POST /v1/chat/sessions`
  - `PATCH /v1/chat/sessions/{chat_id}`
- Required chat write fields:
  - `agent_id`, `user_id`, `chat_id`, `message_id`, `role`

## Matrix

| SimpleAgents | SimpleFlowSDKs | SimpleFlow API Contract | Status | Notes |
| --- | --- | --- | --- | --- |
| `feat/telemetry-sample-rate-enforcement` and later | `main` (this repository, current) | `v1 chat sessions contract` | validated | SDK chat helpers target `/v1/chat/sessions` for list/write/patch behavior. |

## Validation Notes

- Python and Node SDK tests cover `/v1/chat/sessions` list/write/patch and authz helper behavior.
- Go and Python SDK tests cover chat history/session read APIs.

## Versioning Guidance

- If SimpleAgents changes workflow result metadata paths, bump SDK minor version and update mapping notes.
- If SimpleFlow runtime event envelope fields change incompatibly, bump SDK major version and update this matrix in the same change.

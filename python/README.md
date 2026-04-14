# SimpleFlow Python SDK

This SDK helps Python remote runtime backends integrate with the SimpleFlow control plane.

## Features

- API client for auth/session helpers and chat session operations (`list_chat_sessions`, `list_chat_messages`, `write_chat_message`, `update_chat_session`).
- Message output helpers (`get_chat_message_output`, `upsert_chat_message_output`).
- Control-plane auth helpers (`create_auth_session`, `refresh_auth_session`, `validate_access_token`).
- Invoke token verification helper for control-plane issued tokens (HS256 shared key and RS256 public key/JWKS usage).
- Method-level auth token overrides on control-plane and lifecycle methods.
- Typed request errors (`SimpleFlowAuthenticationError`, `SimpleFlowAuthorizationError`, `SimpleFlowLifecycleError`).
- Typed dataclasses for chat payloads.
- Telemetry bridge with `simpleflow` and `otlp` modes.

## Install

```bash
pip install -e ./python
```

## Minimal usage

```python
from simpleflow_sdk import SimpleFlowClient

client = SimpleFlowClient(base_url="https://api.simpleflow.example")

session = await client.create_auth_session(email="user@example.com", password="secret")
user_token = session["access_token"]
principal = await client.validate_access_token(auth_token=user_token)

sessions = await client.list_chat_sessions(
    agent_id="agent_1",
    user_id=principal["user_id"],
    page=1,
    limit=20,
    auth_token=user_token,
)

await client.write_chat_message(
    {
        "agent_id": "agent_1",
        "user_id": principal["user_id"],
        "chat_id": "chat_1",
        "message_id": "m_1",
        "role": "user",
        "content": {"text": "Hello"},
        "telemetry_data": {"source": "web"},
    },
    auth_token=user_token,
)

# Optional: derive assistant message + output_data directly from SimpleAgents result
await client.write_chat_message_from_simple_agents_result(
    agent_id="agent_1",
    user_id=principal["user_id"],
    chat_id="chat_1",
    message_id="m_assistant_1",
    workflow_result=res,
    auth_token=user_token,
)
```

## Notes

- `write_chat_message` requires: `agent_id`, `user_id`, `chat_id`, `message_id`, `role`.
- `output_data` is only valid when `role == "assistant"`.
- Unknown top-level keys in `write_chat_message` payload are rejected by the SDK.
- `list_chat_messages` uses `GET /v1/chat/sessions` with `chat_id` query filtering.
- `user_id` is optional for `list_chat_sessions` and `list_chat_messages` when caller is `admin`/`super_admin`.

# SimpleFlow Python SDK

This SDK helps Python remote runtime backends integrate with the SimpleFlow control plane.

## Features

- API client for auth/session helpers and chat session operations (`list_chat_sessions`, `list_chat_messages`, `write_chat_message`, `update_chat_session`).
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

client = SimpleFlowClient(base_url="https://api.simpleflow.example", api_token="user-jwt")

sessions = await client.list_chat_sessions(
    agent_id="agent_1",
    user_id="user_1",
    page=1,
    limit=20,
)

await client.write_chat_message(
    {
        "agent_id": "agent_1",
        "user_id": "user_1",
        "chat_id": "chat_1",
        "message_id": "m_1",
        "role": "user",
        "content": {"text": "Hello"},
        "telemetry_data": {"source": "web"},
    }
)
```

## Notes

- `write_chat_message` requires: `agent_id`, `user_id`, `chat_id`, `message_id`, `role`.
- `list_chat_messages` uses `GET /v1/chat/sessions` with `chat_id` query filtering.

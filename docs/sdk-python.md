# Python SDK

Package: `simpleflow-sdk`

## Key APIs

- `list_chat_sessions(...)`
- `list_chat_messages(...)`
- `write_chat_message(...)`
- `write_chat_message_from_simple_agents_result(...)`
- `get_chat_message_output(...)`
- `upsert_chat_message_output(...)`
- `update_chat_session(...)`
- `authorize_runtime_chat_read(...)`
- `create_auth_session(...)`
- `refresh_auth_session(...)`
- `validate_access_token(...)`

## Install

```bash
pip install simpleflow-sdk
```

## Minimal example

```python
from simpleflow_sdk import SimpleFlowClient

client = SimpleFlowClient(
    base_url="https://api.simpleflow.example",
)

session = await client.create_auth_session(
    email="user@example.com",
    password="secret",
)
user_token = session["access_token"]
principal = await client.validate_access_token(auth_token=user_token)

await client.write_chat_message(
    {
        "agent_id": "agent_support_v1",
        "user_id": principal["user_id"],
        "chat_id": "chat_123",
        "message_id": "m_123",
        "role": "user",
        "content": {"text": "hello"},
        "telemetry_data": {"source": "python-sdk-docs"},
    }
    auth_token=user_token,
)

await client.write_chat_message_from_simple_agents_result(
    agent_id="agent_support_v1",
    user_id=principal["user_id"],
    chat_id="chat_123",
    message_id="m_assistant_123",
    workflow_result=res,
    auth_token=user_token,
)

output = await client.get_chat_message_output(
    message_id="m_assistant_123",
    agent_id="agent_support_v1",
    chat_id="chat_123",
    user_id=principal["user_id"],
    auth_token=user_token,
)
```

## Integration guide

- See full auth + telemetry + chat + workflow setup: [Python Integration](/sdk-python-integration)

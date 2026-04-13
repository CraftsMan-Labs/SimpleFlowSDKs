# Python SDK

Package: `simpleflow-sdk`

## Key APIs

- `list_chat_sessions(...)`
- `list_chat_messages(...)`
- `write_chat_message(...)`
- `update_chat_session(...)`
- `authorize_runtime_chat_read(...)`

## Install

```bash
pip install simpleflow-sdk
```

## Minimal example

```python
from simpleflow_sdk import SimpleFlowClient

client = SimpleFlowClient(
    base_url="https://api.simpleflow.example",
    api_token="<token>",
)

await client.write_chat_message(
    {
        "agent_id": "agent_support_v1",
        "user_id": "user_123",
        "chat_id": "chat_123",
        "message_id": "m_123",
        "role": "user",
        "content": {"text": "hello"},
        "telemetry_data": {"source": "python-sdk-docs"},
    }
)
```

## Integration guide

- See full auth + telemetry + chat + workflow setup: [Python Integration](/sdk-python-integration)

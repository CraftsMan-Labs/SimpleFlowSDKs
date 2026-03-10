# Python SDK

Package: `simpleflow-sdk`

## Key APIs

- `write_event(...)`
- `write_chat_message(...)`
- `publish_queue_contract(...)`
- `write_event_from_workflow_result(...)`
- `write_chat_message_from_workflow_result(...)`
- `with_telemetry(...).emit_span(...)`

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

client.write_event(
    {
        "event_type": "runtime.workflow.completed",
        "agent_id": "agent_support_v1",
        "organization_id": "org_123",
        "user_id": "user_123",
        "run_id": "run_123",
        "payload": {"source": "python-sdk-docs"},
    }
)
```

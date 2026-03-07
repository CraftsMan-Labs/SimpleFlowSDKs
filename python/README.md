# SimpleFlow Python SDK (Remote Runtime)

This SDK helps Python remote runtime backends integrate with the SimpleFlow control plane.

## Features

- API client for runtime events, chat message writes, and queue contract publication.
- Invoke token verification helper for control-plane issued tokens.
- Typed dataclasses for common runtime payloads.

## Install

```bash
pip install -e ./sdk/python
```

## Minimal usage

```python
from simpleflow_sdk import RuntimeEvent, SimpleFlowClient

client = SimpleFlowClient(base_url="https://api.simpleflow.example", api_token="runtime-token")
client.report_runtime_event(
    RuntimeEvent(
        type="runtime.invoke.accepted",
        agent_id="agent-1",
        agent_version="v1",
        run_id="run_123",
    )
)
```

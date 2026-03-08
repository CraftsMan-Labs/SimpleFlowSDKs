# SimpleFlow Python SDK (Remote Runtime)

This SDK helps Python remote runtime backends integrate with the SimpleFlow control plane.

## Features

- API client for runtime registration, invoke, runtime events, chat message writes, and queue contract publication.
- Invoke token verification helper for control-plane issued tokens.
- Typed dataclasses for common runtime payloads and telemetry span envelopes.
- Telemetry bridge with `simpleflow` and `otlp` modes.

## Install

```bash
pip install -e ./python
```

## Minimal usage

```python
from simpleflow_sdk import RuntimeEvent, SimpleFlowClient

client = SimpleFlowClient(base_url="https://api.simpleflow.example", api_token="runtime-token")
client.write_event(
    RuntimeEvent(
        type="runtime.invoke.accepted",
        agent_id="agent-1",
        run_id="run_123"
    )
)

telemetry = client.with_telemetry(mode="simpleflow", sample_rate=0.2)
telemetry.emit_span(
    span={"name": "llm.call", "start_time_ms": 1000, "end_time_ms": 1250},
    trace_id="trace_123",
    run_id="run_123",
    agent_id="agent-1",
)
```

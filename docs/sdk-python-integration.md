# Python SDK Integration Guide

This page shows the end-to-end integration flow for auth, telemetry, chat, and running workflows with SimpleAgents.

## Auth overview

- Machine auth (runtime connect + runtime writes): use either `SIMPLEFLOW_API_TOKEN` or set `MACHINE_CLIENT_ID` + `MACHINE_CLIENT_SECRET` and let the SDK fetch OAuth token from `/v1/oauth/token`.
- User auth (runtime invoke): user bearer token hits `/v1/runtime/invoke`; control plane forwards it to your runtime.
- Chat entrypoint (`/api/v1/chat`): accepts **API key** (`agk_*`) or **user bearer**. `agent_id` is required in the body.

## Auth env options

Option A - static token:

```bash
export SIMPLEFLOW_BASE_URL="http://localhost:8080"
export SIMPLEFLOW_API_TOKEN="<machine_runtime_token>"
```

Option B - client credentials:

```bash
export SIMPLEFLOW_BASE_URL="http://localhost:8080"
export MACHINE_CLIENT_ID="<machine_client_id>"
export MACHINE_CLIENT_SECRET="<machine_client_secret>"
```

## Runtime connect

```python
import os

from simpleflow_sdk import SimpleFlowClient

client = SimpleFlowClient(
    base_url=os.environ["SIMPLEFLOW_BASE_URL"],
    api_token=os.getenv("SIMPLEFLOW_API_TOKEN"),
    oauth_client_id=os.getenv("MACHINE_CLIENT_ID"),
    oauth_client_secret=os.getenv("MACHINE_CLIENT_SECRET"),
    runtime_register_path="/v1/runtime/connect",
)

client.register_runtime(
    {
        "agent_id": os.environ["SIMPLEFLOW_AGENT_ID"],
        "agent_version": os.environ["SIMPLEFLOW_AGENT_VERSION"],
        "endpoint_url": os.environ["RUNTIME_ENDPOINT_URL"],
        "auth_mode": "jwt",
        "capabilities": ["chat", "webhook", "queue"],
        "runtime_id": os.environ["SIMPLEFLOW_RUNTIME_ID"],
    }
)
```

## Telemetry (workflow result)

```python
client.write_event_from_workflow_result(
    agent_id=os.environ["SIMPLEFLOW_AGENT_ID"],
    workflow_result=workflow_result,
)
```

## Telemetry (spans)

```python
telemetry = client.with_telemetry(mode="simpleflow", sample_rate=1.0)
telemetry.emit_span(
    span={"name": "llm.call", "start_time_ms": 1000, "end_time_ms": 1450},
    trace_id="trace_123",
    run_id="run_123",
    agent_id=os.environ["SIMPLEFLOW_AGENT_ID"],
)
```

## Chat entrypoint (`/api/v1/chat`)

```python
import requests

resp = requests.post(
    f"{os.environ['SIMPLEFLOW_BASE_URL']}/api/v1/chat",
    headers={
        "Authorization": f"Bearer {os.environ['SIMPLEFLOW_API_KEY_OR_USER_TOKEN']}",
        "Content-Type": "application/json",
    },
    json={
        "agent_id": os.environ["SIMPLEFLOW_AGENT_ID"],
        "agent_version": os.environ["SIMPLEFLOW_AGENT_VERSION"],
        "message": "hello",
    },
    timeout=30,
)
resp.raise_for_status()
data = resp.json()
```

## Chat history (SDK)

```python
created = client.create_chat_history_message(
    agent_id=os.environ["SIMPLEFLOW_AGENT_ID"],
    chat_id="chat_123",
    user_id="user_123",
    role="user",
    content={"text": "hello"},
    metadata={"source": "web"},
    auth_token=os.environ["SIMPLEFLOW_USER_BEARER"],
)

messages = client.list_chat_history_messages(
    agent_id=os.environ["SIMPLEFLOW_AGENT_ID"],
    chat_id="chat_123",
    user_id="user_123",
    auth_token=os.environ["SIMPLEFLOW_USER_BEARER"],
)
```

## Run workflows with SimpleAgents + send telemetry

```python
from simple_agents_py import Client as AgentsClient

agents = AgentsClient()
workflow_result = agents.run_workflow_yaml(
    os.environ["WORKFLOW_PATH"],
    {"email_text": "hello"},
    workflow_options={
        "telemetry": {"enabled": True, "sample_rate": 1.0},
        "trace": {
            "tenant": {
                "organization_id": os.environ["SIMPLEFLOW_ORGANIZATION_ID"],
                "user_id": "user_123",
                "conversation_id": "chat_123",
                "request_id": "req_123",
                "run_id": "run_123",
            }
        },
    },
)

client.write_event_from_workflow_result(
    agent_id=os.environ["SIMPLEFLOW_AGENT_ID"],
    workflow_result=workflow_result,
)
```

## Minimal env

- `SIMPLEFLOW_BASE_URL`
- `SIMPLEFLOW_API_TOKEN` or (`MACHINE_CLIENT_ID` + `MACHINE_CLIENT_SECRET`)
- `SIMPLEFLOW_AGENT_ID`
- `SIMPLEFLOW_AGENT_VERSION`
- `SIMPLEFLOW_RUNTIME_ID`
- `SIMPLEFLOW_ORGANIZATION_ID`
- `RUNTIME_ENDPOINT_URL`
- `WORKFLOW_PATH`

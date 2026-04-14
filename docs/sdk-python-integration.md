# Python SDK Integration Guide

This page shows the end-to-end integration flow for auth, telemetry, chat, and running workflows with SimpleAgents.

Shared auth and env model: [SDK Integration Common Guide](/sdk-integration-common)

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

## Chat sessions (SDK)

```python
session = await client.create_auth_session(
    email=os.environ["SIMPLEFLOW_USER_EMAIL"],
    password=os.environ["SIMPLEFLOW_USER_PASSWORD"],
)
user_token = session["access_token"]
principal = await client.validate_access_token(auth_token=user_token)

await client.write_chat_message(
    {
        "agent_id": os.environ["SIMPLEFLOW_AGENT_ID"],
        "chat_id": "chat_123",
        "user_id": principal["user_id"],
        "message_id": "m_123",
        "role": "user",
        "content": {"text": "hello"},
        "telemetry_data": {"source": "web"},
    },
    auth_token=user_token,
)

messages = await client.list_chat_messages(
    agent_id=os.environ["SIMPLEFLOW_AGENT_ID"],
    chat_id="chat_123",
    user_id=principal["user_id"],
    auth_token=user_token,
)

await client.update_chat_session(
    chat_id="chat_123",
    agent_id=os.environ["SIMPLEFLOW_AGENT_ID"],
    user_id=principal["user_id"],
    status="active",
    auth_token=user_token,
)

await client.refresh_auth_session()

await client.write_chat_message_from_simple_agents_result(
    agent_id=os.environ["SIMPLEFLOW_AGENT_ID"],
    user_id=principal["user_id"],
    chat_id="chat_123",
    message_id="m_assistant_123",
    workflow_result=workflow_result,
    auth_token=user_token,
)

output = await client.get_chat_message_output(
    message_id="m_assistant_123",
    agent_id=os.environ["SIMPLEFLOW_AGENT_ID"],
    chat_id="chat_123",
    user_id=principal["user_id"],
    auth_token=user_token,
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

Use the shared list in [SDK Integration Common Guide](/sdk-integration-common#shared-env-variables).

Python-specific reminder:

- `SIMPLEFLOW_API_KEY_OR_USER_TOKEN` for direct `/api/v1/chat` calls.

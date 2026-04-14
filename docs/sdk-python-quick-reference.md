# SimpleFlow Python SDK Quick Reference

## Installation
```bash
pip install -e python/  # From SDK repo root
```

## Required Environment Variables
```bash
SIMPLEFLOW_BASE_URL=http://localhost:8080
SIMPLEFLOW_USER_EMAIL=user@example.com
SIMPLEFLOW_USER_PASSWORD=secret123
SIMPLEFLOW_AGENT_ID=optional-agent-id
```

## Quick Start Template

```python
import asyncio
import os
import uuid
from dotenv import load_dotenv
from simpleflow_sdk import SimpleFlowClient

load_dotenv()

async def main():
    # 1. Initialize
    client = SimpleFlowClient(base_url=os.environ["SIMPLEFLOW_BASE_URL"])
    
    # 2. Login (one-time)
    session = await client.create_auth_session(
        email=os.environ["SIMPLEFLOW_USER_EMAIL"],
        password=os.environ["SIMPLEFLOW_USER_PASSWORD"],
    )
    token = session["access_token"]
    
    # 3. Get user info
    principal = await client.validate_access_token(auth_token=token)
    user_id = principal["user_id"]
    agent_id = os.environ.get("SIMPLEFLOW_AGENT_ID", "auto-discover")
    chat_id = f"chat_{uuid.uuid4().hex[:10]}"
    
    # 4. Write user message
    user_msg_id = f"user_{uuid.uuid4().hex[:10]}"
    await client.write_chat_message(
        {
            "agent_id": agent_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "message_id": user_msg_id,
            "role": "user",
            "content": {"text": "Hello!"},
            "telemetry_data": {"source": "quickstart"},
        },
        auth_token=token,
    )
    
    # 5. Write assistant with workflow result
    assistant_id = f"assistant_{uuid.uuid4().hex[:10]}"
    workflow_result = {
        "workflow_id": "demo",
        "terminal_output": {"result": "success"},
        # ... other fields
    }
    
    await client.write_chat_message_from_simple_agents_result(
        agent_id=agent_id,
        user_id=user_id,
        chat_id=chat_id,
        message_id=assistant_id,
        workflow_result=workflow_result,
        auth_token=token,
    )
    
    # 6. Read back
    messages = await client.list_chat_messages(
        agent_id=agent_id, chat_id=chat_id, user_id=user_id, auth_token=token
    )
    output = await client.get_chat_message_output(
        message_id=assistant_id, agent_id=agent_id, chat_id=chat_id, 
        user_id=user_id, auth_token=token
    )
    
    print(f"Messages: {len(messages)}, Output keys: {list(output.get('output', {}).keys())}")

asyncio.run(main())
```

## Core Methods

| Method | Purpose | Key Params |
|--------|---------|-----------|
| `create_auth_session()` | Login with email/password | `email`, `password` |
| `validate_access_token()` | Verify token, get user info | `auth_token` |
| `refresh_auth_session()` | Refresh expired token | - |
| `list_chat_sessions()` | Get user's chat sessions | `agent_id`, `user_id` |
| `list_chat_messages()` | Get messages in a chat | `agent_id`, `chat_id`, `user_id` |
| `write_chat_message()` | Write any message | payload dict, `auth_token` |
| `write_chat_message_from_simple_agents_result()` | Write assistant with workflow output | `agent_id`, `user_id`, `chat_id`, `message_id`, `workflow_result` |
| `get_chat_message_output()` | Read persisted output | `message_id`, `agent_id`, `chat_id`, `user_id` |
| `update_chat_session()` | Update chat metadata | `chat_id`, `status` |

## Message Roles
- `user` - Human user messages
- `assistant` - AI/agent responses (only role that can have `output_data`)
- `system` - System instructions
- `tool` - Tool/function results

## Strict Schema Rules
- Only these top-level keys allowed: `agent_id`, `user_id`, `chat_id`, `message_id`, `role`, `content`, `telemetry_data`, `output_data`
- `output_data` only valid for `role="assistant"`
- Unknown keys rejected with error

## Common Patterns

### Reuse Token
```python
# Store token after login, reuse for all calls
token = session["access_token"]
# ... use token in all subsequent calls
```

### Handle Expired Token
```python
try:
    result = await some_api_call(auth_token=token)
except SimpleFlowAuthenticationError:
    # Token expired, refresh
    new_session = await client.refresh_auth_session()
    token = new_session["access_token"]
    result = await some_api_call(auth_token=token)
```

### Batch Workflow Results
```python
# Process multiple documents, create one chat per document
for doc in documents:
    chat_id = f"chat_{uuid.uuid4().hex[:10]}"
    
    # Write user message
    await client.write_chat_message(...)
    
    # Run workflow and write result
    result = run_workflow(doc)
    await client.write_chat_message_from_simple_agents_result(
        chat_id=chat_id, ...
    )
```

## Error Handling
```python
from simpleflow_sdk import (
    SimpleFlowAuthenticationError,
    SimpleFlowAuthorizationError,
    SimpleFlowRequestError,
)

try:
    result = await client.write_chat_message(...)
except SimpleFlowAuthenticationError as e:
    print(f"Auth failed: {e.detail}")
except SimpleFlowAuthorizationError as e:
    print(f"Permission denied: {e.detail}")
except SimpleFlowRequestError as e:
    print(f"Request failed: {e.status_code} - {e.detail}")
```

## Full Documentation
- Step-by-step guide: `docs/sdk-python-integration-step-by-step.md`
- API reference: `docs/sdk-python.md`
- Working example: `examples/python-simpleagents-chat/`

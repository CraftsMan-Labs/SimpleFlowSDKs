# Python SDK Integration Guide (Step-by-Step)

This guide walks you through integrating with SimpleFlow using the Python SDK, from installation to full chat session management with SimpleAgents workflow results.

## Prerequisites

- Python 3.11 or higher
- A running SimpleFlow control plane (local or remote)
- User credentials (email and password) for the control plane

---

## Step 1: Install the SDK

### Option A: Install from local repository (development)

```bash
# Clone the SDK repository
git clone https://github.com/CraftsMan-Labs/SimpleFlowSDKs.git
cd SimpleFlowSDKs/python

# Install in editable mode
pip install -e .
```

### Option B: Install from PyPI (when published)

```bash
pip install simpleflow-sdk
```

---

## Step 2: Configure Environment Variables

Create a `.env` file or export these variables in your shell:

```bash
# Required: Control plane URL
export SIMPLEFLOW_BASE_URL="http://localhost:8080"  # or your remote URL

# Required: User credentials for authentication
export SIMPLEFLOW_USER_EMAIL="your-email@example.com"
export SIMPLEFLOW_USER_PASSWORD="your-password"

# Optional: Pre-configured agent ID (otherwise auto-discovered)
export SIMPLEFLOW_AGENT_ID="your-agent-id"
```

Load environment variables in Python:

```python
import os
from dotenv import load_dotenv

load_dotenv()  # Loads from .env file

BASE_URL = os.environ["SIMPLEFLOW_BASE_URL"]
USER_EMAIL = os.environ["SIMPLEFLOW_USER_EMAIL"]
USER_PASSWORD = os.environ["SIMPLEFLOW_USER_PASSWORD"]
```

---

## Step 3: Initialize the Client

```python
from simpleflow_sdk import SimpleFlowClient

# Create client instance
client = SimpleFlowClient(
    base_url=BASE_URL,
    # Optional: For machine-to-machine auth (not needed for user-scoped APIs)
    # api_token="machine-token",
    # oauth_client_id="client-id",
    # oauth_client_secret="client-secret",
)
```

---

## Step 4: Authenticate and Get Access Token

All user-scoped operations require a bearer token obtained via email/password login:

```python
import asyncio

async def authenticate():
    # Login with email/password (one-time)
    session = await client.create_auth_session(
        email=USER_EMAIL,
        password=USER_PASSWORD,
    )
    
    # Extract the access token
    access_token = session["access_token"]
    
    # Validate the token and get user info
    principal = await client.validate_access_token(auth_token=access_token)
    user_id = principal["user_id"]
    
    print(f"Authenticated as user: {user_id}")
    return access_token, user_id

# Run in async context
access_token, user_id = asyncio.run(authenticate())
```

**Important**: Store this `access_token` and reuse it for all subsequent API calls. The email/password should only be used once to obtain the token.

---

## Step 5: Discover or Specify Agent ID

If you don't know your agent ID, auto-discover it:

```python
async def get_agent_id(access_token):
    # Option 1: Use pre-configured agent ID
    agent_id = os.environ.get("SIMPLEFLOW_AGENT_ID")
    if agent_id:
        return agent_id
    
    # Option 2: List available agents and pick first
    async with httpx.AsyncClient() as http:
        response = await http.get(
            f"{BASE_URL}/api/v1/agents",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        agents = response.json()
        
        if isinstance(agents, list) and len(agents) > 0:
            # Use first agent's ID
            return agents[0].get("ID") or agents[0].get("id")
        else:
            raise ValueError("No agents available")

agent_id = asyncio.run(get_agent_id(access_token))
```

---

## Step 6: Create a Chat Session

```python
import uuid

# Generate a unique chat ID or use an existing one
chat_id = f"chat_{uuid.uuid4().hex[:10]}"

# Or list existing sessions
async def list_sessions():
    sessions = await client.list_chat_sessions(
        agent_id=agent_id,
        user_id=user_id,
        auth_token=access_token,
    )
    return sessions

# Get or create chat
async def get_or_create_chat():
    sessions = await list_sessions()
    if sessions:
        return sessions[0]["chat_id"]  # Use existing
    return chat_id  # Use new

chat_id = asyncio.run(get_or_create_chat())
```

---

## Step 7: Write a User Message

```python
import uuid

async def write_user_message(user_text):
    message_id = f"user_{uuid.uuid4().hex[:10]}"
    
    result = await client.write_chat_message(
        {
            "agent_id": agent_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "role": "user",
            "content": {"text": user_text},
            "telemetry_data": {
                "source": "my-app",
                "event_type": "user.message",
            },
        },
        auth_token=access_token,
    )
    
    return message_id, result

user_message_id, _ = asyncio.run(
    write_user_message("Please classify this invoice and summarize the findings.")
)
```

**Validation Rules**:
- `role` must be one of: `system`, `user`, `assistant`, `tool`
- `output_data` is only allowed when `role` is `assistant`
- Unknown top-level keys are rejected (strict schema)

---

## Step 8: Run SimpleAgents Workflow and Write Assistant Response

This is the main integration point between SimpleAgents and SimpleFlow.

### Option A: Use Live Workflow

```python
from simple_agents_py import Client as SimpleAgentsClient
from simple_agents_py.workflow_payload import workflow_execution_request_to_mapping
from simple_agents_py.workflow_request import (
    WorkflowExecutionRequest,
    WorkflowMessage,
    WorkflowRole,
)

async def run_workflow_and_write_response(user_input):
    # Initialize SimpleAgents client
    agents_client = SimpleAgentsClient(
        provider=os.environ["WORKFLOW_PROVIDER"],  # e.g., "openai"
        api_base=os.environ["WORKFLOW_API_BASE"],
        api_key=os.environ["WORKFLOW_API_KEY"],
    )
    
    # Create workflow request
    workflow_file = "/path/to/your/workflow.yaml"
    request = WorkflowExecutionRequest(
        workflow_path=workflow_file,
        messages=[WorkflowMessage(role=WorkflowRole.USER, content=user_input)],
    )
    
    # Execute workflow
    result = agents_client.run_workflow(
        workflow_execution_request_to_mapping(request)
    )
    
    # Write assistant message with workflow result
    assistant_message_id = f"assistant_{uuid.uuid4().hex[:10]}"
    
    await client.write_chat_message_from_simple_agents_result(
        agent_id=agent_id,
        user_id=user_id,
        chat_id=chat_id,
        message_id=assistant_message_id,
        workflow_result=result,  # Full SimpleAgents result object
        auth_token=access_token,
    )
    
    return assistant_message_id, result

assistant_id, workflow_result = asyncio.run(
    run_workflow_and_write_response("Classify this document")
)
```

### Option B: Use Sample/Pre-computed Workflow Result

```python
import json

# Load a pre-computed workflow result
with open("workflow_result.json") as f:
    workflow_result = json.load(f)

async def write_from_precomputed_result():
    assistant_message_id = f"assistant_{uuid.uuid4().hex[:10]}"
    
    await client.write_chat_message_from_simple_agents_result(
        agent_id=agent_id,
        user_id=user_id,
        chat_id=chat_id,
        message_id=assistant_message_id,
        workflow_result=workflow_result,
        auth_token=access_token,
    )
    
    return assistant_message_id

assistant_id = asyncio.run(write_from_precomputed_result())
```

**What the helper does**:
1. Extracts `terminal_output` for the message `content.text`
2. Builds `telemetry_data` from workflow metrics (latency, tokens, model)
3. Sanitizes the full result into strict `output_data` format:
   - `workflow_id`, `trace_id`, `trace`
   - `outputs` (node-level outputs)
   - `llm_node_metrics` and `llm_node_models`
   - `terminal_output`, `total_*` metrics
   - `metadata.telemetry` and `metadata.trace.tenant`
4. Sets `role` to `assistant`

---

## Step 9: Read Chat History and Verify Output

```python
async def read_chat_and_verify(assistant_message_id):
    # List all messages in the chat
    messages = await client.list_chat_messages(
        agent_id=agent_id,
        chat_id=chat_id,
        user_id=user_id,
        auth_token=access_token,
    )
    
    print(f"Total messages: {len(messages)}")
    
    # Get persisted output for assistant message
    output = await client.get_chat_message_output(
        message_id=assistant_message_id,
        agent_id=agent_id,
        chat_id=chat_id,
        user_id=user_id,
        auth_token=access_token,
    )
    
    print(f"Output keys: {sorted(output.get('output', {}).keys())}")
    
    # List all sessions for the user
    sessions = await client.list_chat_sessions(
        agent_id=agent_id,
        user_id=user_id,
        auth_token=access_token,
    )
    
    print(f"Total sessions: {len(sessions)}")
    
    return messages, output, sessions

messages, output, sessions = asyncio.run(
    read_chat_and_verify(assistant_id)
)
```

---

## Step 10: Update Chat Session Metadata

```python
async def update_session():
    await client.update_chat_session(
        chat_id=chat_id,
        agent_id=agent_id,
        user_id=user_id,
        status="active",  # or "archived", "closed"
        # title="Invoice Classification Chat",
        auth_token=access_token,
    )

asyncio.run(update_session())
```

---

## Step 11: Refresh Token When Needed

If your session expires, refresh without re-entering password:

```python
async def refresh_token():
    # Uses stored refresh cookie from previous login
    new_session = await client.refresh_auth_session()
    new_token = new_session["access_token"]
    
    # Update your stored token
    global access_token
    access_token = new_token
    
    return new_token

# When needed (e.g., on 401 errors)
# new_token = asyncio.run(refresh_token())
```

**Note**: Requires the client to have been initialized and `create_auth_session` called previously (stores refresh cookie internally).

---

## Complete Integration Example

```python
#!/usr/bin/env python3
"""
Complete SimpleFlow + SimpleAgents integration example.
"""

import asyncio
import json
import os
import uuid
from dotenv import load_dotenv

from simpleflow_sdk import SimpleFlowClient
from simple_agents_py import Client as SimpleAgentsClient
from simple_agents_py.workflow_payload import workflow_execution_request_to_mapping
from simple_agents_py.workflow_request import (
    WorkflowExecutionRequest,
    WorkflowMessage,
    WorkflowRole,
)

load_dotenv()


class SimpleFlowIntegration:
    def __init__(self):
        self.client = SimpleFlowClient(
            base_url=os.environ["SIMPLEFLOW_BASE_URL"]
        )
        self.access_token = None
        self.user_id = None
        self.agent_id = None
        self.chat_id = None
        
    async def authenticate(self):
        """Step 1: Login and get access token."""
        session = await self.client.create_auth_session(
            email=os.environ["SIMPLEFLOW_USER_EMAIL"],
            password=os.environ["SIMPLEFLOW_USER_PASSWORD"],
        )
        self.access_token = session["access_token"]
        
        principal = await self.client.validate_access_token(
            auth_token=self.access_token
        )
        self.user_id = principal["user_id"]
        print(f"✓ Authenticated as: {self.user_id}")
        
    async def setup_agent(self):
        """Step 2: Get or set agent ID."""
        self.agent_id = os.environ.get("SIMPLEFLOW_AGENT_ID")
        if not self.agent_id:
            # Auto-discover from API
            import httpx
            async with httpx.AsyncClient() as http:
                response = await http.get(
                    f"{os.environ['SIMPLEFLOW_BASE_URL']}/api/v1/agents",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                response.raise_for_status()
                agents = response.json()
                if agents:
                    self.agent_id = agents[0].get("ID") or agents[0].get("id")
        print(f"✓ Using agent: {self.agent_id}")
        
    async def create_chat(self):
        """Step 3: Create a new chat session."""
        self.chat_id = f"chat_{uuid.uuid4().hex[:10]}"
        print(f"✓ Created chat: {self.chat_id}")
        
    async def write_user_message(self, text):
        """Step 4: Write user message."""
        message_id = f"user_{uuid.uuid4().hex[:10]}"
        
        await self.client.write_chat_message(
            {
                "agent_id": self.agent_id,
                "user_id": self.user_id,
                "chat_id": self.chat_id,
                "message_id": message_id,
                "role": "user",
                "content": {"text": text},
                "telemetry_data": {"source": "integration-example"},
            },
            auth_token=self.access_token,
        )
        print(f"✓ Wrote user message: {message_id}")
        return message_id
        
    async def run_workflow_and_write_response(self, user_input):
        """Step 5: Run SimpleAgents and write assistant response."""
        # Run workflow
        agents_client = SimpleAgentsClient(
            provider=os.environ["WORKFLOW_PROVIDER"],
            api_base=os.environ["WORKFLOW_API_BASE"],
            api_key=os.environ["WORKFLOW_API_KEY"],
        )
        
        request = WorkflowExecutionRequest(
            workflow_path=os.environ["WORKFLOW_PATH"],
            messages=[WorkflowMessage(role=WorkflowRole.USER, content=user_input)],
        )
        
        result = agents_client.run_workflow(
            workflow_execution_request_to_mapping(request)
        )
        
        # Write assistant message with result
        assistant_id = f"assistant_{uuid.uuid4().hex[:10]}"
        
        await self.client.write_chat_message_from_simple_agents_result(
            agent_id=self.agent_id,
            user_id=self.user_id,
            chat_id=self.chat_id,
            message_id=assistant_id,
            workflow_result=result,
            auth_token=self.access_token,
        )
        
        print(f"✓ Wrote assistant message: {assistant_id}")
        print(f"✓ Workflow result keys: {list(result.keys())}")
        return assistant_id, result
        
    async def verify_and_summarize(self, assistant_id):
        """Step 6: Read chat history and verify output."""
        messages = await self.client.list_chat_messages(
            agent_id=self.agent_id,
            chat_id=self.chat_id,
            user_id=self.user_id,
            auth_token=self.access_token,
        )
        
        output = await self.client.get_chat_message_output(
            message_id=assistant_id,
            agent_id=self.agent_id,
            chat_id=self.chat_id,
            user_id=self.user_id,
            auth_token=self.access_token,
        )
        
        sessions = await self.client.list_chat_sessions(
            agent_id=self.agent_id,
            user_id=self.user_id,
            auth_token=self.access_token,
        )
        
        print(f"\n=== Integration Summary ===")
        print(f"Total messages: {len(messages)}")
        print(f"Total sessions: {len(sessions)}")
        print(f"Output data keys: {sorted(output.get('output', {}).keys())}")
        print(f"\nTerminal output preview:")
        terminal = output.get('output', {}).get('terminal_output', {})
        print(json.dumps(terminal, indent=2)[:500] + "...")
        
    async def run(self, user_input):
        """Run complete integration flow."""
        await self.authenticate()
        await self.setup_agent()
        await self.create_chat()
        await self.write_user_message(user_input)
        assistant_id, result = await self.run_workflow_and_write_response(user_input)
        await self.verify_and_summarize(assistant_id)
        print("\n✓ Integration complete!")


# Run the integration
if __name__ == "__main__":
    integration = SimpleFlowIntegration()
    asyncio.run(integration.run("Classify this invoice document"))
```

---

## Troubleshooting

### Authentication Errors (401)

```python
# Check if token is valid
principal = await client.validate_access_token(auth_token=access_token)
if not principal.get("user_id"):
    # Re-authenticate
    session = await client.create_auth_session(email=email, password=password)
    access_token = session["access_token"]
```

### Strict Schema Errors

If you get "unknown keys in chat message payload":

```python
# Only allowed keys: agent_id, user_id, chat_id, message_id, role, content, telemetry_data, output_data
# Remove any extra fields from your payload
```

If you get "output_data is only allowed when role is assistant":

```python
# output_data can only be used with role="assistant"
# For user messages, omit output_data entirely
```

### Missing Dependencies

```bash
# Install required dependencies
pip install httpx PyJWT

# For SimpleAgents integration (optional)
pip install simple-agents-py

# For environment loading (optional)
pip install python-dotenv
```

---

## Next Steps

1. **Explore the examples**: Check `examples/python-simpleagents-chat/` in the SDK repository for runnable reference code
2. **Read the API docs**: See `docs/sdk-python.md` for complete API reference
3. **Review the tests**: Look at `python/tests/test_client.py` for usage patterns
4. **Integration patterns**: Review this guide's "Complete Integration Example" section for production-ready patterns

---

## Key Principles

1. **Token-first**: Use email/password only once to get a token, then use the token for everything
2. **Strict schema**: The SDK enforces strict validation - only use documented fields
3. **Async everywhere**: All SDK methods are async and must be run with `asyncio.run()` or in an async context
4. **Assistant-only output_data**: Only assistant messages can include workflow output_data
5. **Reuse credentials**: Store and reuse the access_token; refresh when needed instead of re-logging in

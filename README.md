# SimpleFlow SDKs

Minimal SDKs for connecting chat applications to the SimpleFlow control plane.

## Quick Start

### 1) Install an SDK

```bash
# JavaScript / TypeScript
npm install simpleflow-sdk

# Python
pip install simpleflow-sdk
```

### 2) Configure Environment

```bash
export SIMPLEFLOW_BASE_URL="http://localhost:8080"
export SIMPLEFLOW_API_TOKEN="your_machine_token"  # For machine auth
```

### 3) Usage

The SDK supports user authentication via JWT bearer tokens for chat applications.

#### Node.js

```javascript
const { SimpleFlowClient } = require('simpleflow-sdk');

const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL,
});

// Chat app user flow
async function chatFlow(userToken, agentId, userId) {
  // 1. List user's chat sessions
  const sessions = await client.listChatSessions({
    agentId,
    userId,
    authToken: userToken,  // User's JWT/bearer token
  });
  
  const sessionId = sessions[0]?.chat_id || 'new-session';
  
  // 2. Write a chat message
  await client.writeChatMessage({
    agent_id: agentId,
    organization_id: 'org_123',
    user_id: userId,
    chat_id: sessionId,
    role: 'user',
    content: { text: 'Hello!' },
    metadata: { source: 'chat.app' },
  }, { authToken: userToken });
  
  // 3. Store telemetry for the message
  await client.writeMessageTelemetry(
    agentId,
    sessionId,
    {
      total_tokens: 150,
      ttfs: 250,  // Time to first token in ms
      prompt_tokens: 50,
      completion_tokens: 100,
      user_id: userId,
    },
    userToken
  );
}
```

#### Python

```python
import asyncio
from simpleflow_sdk import SimpleFlowClient

client = SimpleFlowClient(base_url="http://localhost:8080")

async def chat_flow(user_token: str, agent_id: str, user_id: str):
    # 1. List user's chat sessions
    sessions = await client.list_chat_sessions(
        agent_id=agent_id,
        user_id=user_id,
        auth_token=user_token,
    )
    
    session_id = sessions[0]["chat_id"] if sessions else "new-session"
    
    # 2. Write a chat message
    await client.write_chat_message({
        "agent_id": agent_id,
        "organization_id": "org_123",
        "user_id": user_id,
        "chat_id": session_id,
        "role": "user",
        "content": {"text": "Hello!"},
        "metadata": {"source": "chat.app"},
    })
    
    # 3. Store telemetry for the message
    await client.write_message_telemetry(
        agent_id=agent_id,
        session_id=session_id,
        metrics={
            "total_tokens": 150,
            "ttfs": 250,
            "prompt_tokens": 50,
            "completion_tokens": 100,
            "user_id": user_id,
        },
        auth_token=user_token,
    )
```

## API Surface

### Chat Operations

- `listChatSessions()` / `list_chat_sessions()` - List chat sessions for a user
- `listChatMessages()` / `list_chat_messages()` - List messages in a chat session
- `writeChatMessage()` / `write_chat_message()` - Store a chat message

### Telemetry

- `writeEvent()` / `write_event()` - Write telemetry event
- `writeMessageTelemetry()` / `write_message_telemetry()` - Write message metrics (total_tokens, ttfs)

### Auth

All chat methods accept an `authToken` parameter for user JWT/bearer token authentication.

## Code Layout

- `node/simpleflow_sdk` - Node.js SDK package
- `python/simpleflow_sdk` - Python SDK package
- `docs/` - Documentation

## Developer Commands

```bash
# Run tests
make test-node
make test-python

# Lint and format
make lint-go
make fmt-go

# Publish (maintainers only)
make publish-node
make publish-python
```

## Endpoints Used

- `GET /v1/runtime/chat/sessions` - List chat sessions
- `GET /v1/runtime/chat/messages/list` - List chat messages
- `POST /v1/runtime/chat/messages` - Write chat message
- `POST /v1/runtime/events` - Write telemetry event

## License

See LICENSE file.

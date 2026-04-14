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
export SIMPLEFLOW_USER_EMAIL="user@example.com"
export SIMPLEFLOW_USER_PASSWORD="secret"
```

### 3) Usage

The SDK supports control-plane auth sessions (`/v1/auth/sessions`) and bearer-token chat calls.

#### Node.js

```javascript
const { SimpleFlowClient } = require('simpleflow-sdk');

const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL,
});

// Chat app user flow
async function chatFlow(agentId) {
  const session = await client.createAuthSession({
    email: process.env.SIMPLEFLOW_USER_EMAIL,
    password: process.env.SIMPLEFLOW_USER_PASSWORD,
  });
  const userToken = session.access_token;
  const principal = await client.validateAccessToken({ authToken: userToken });
  const userId = principal.user_id;

  // 1. List user's chat sessions
  const sessions = await client.listChatSessions({
    agentId,
    userId,
    authToken: userToken,
  });
  
  const sessionId = sessions[0]?.chat_id || 'new-session';
  
  // 2. Write a chat message
  await client.writeChatMessage({
    agent_id: agentId,
    user_id: userId,
    chat_id: sessionId,
    message_id: 'm_001',
    role: 'user',
    content: { text: 'Hello!' },
    telemetry_data: { source: 'chat.app' },
  }, { authToken: userToken });

  // 3. Update session status/title if needed
  await client.updateChatSession({
    chatId: sessionId,
    agentId,
    userId,
    status: 'active',
    authToken: userToken,
  });

  // 4. Refresh when needed
  await client.refreshAuthSession();
}
```

#### Python

```python
import asyncio
from simpleflow_sdk import SimpleFlowClient

client = SimpleFlowClient(base_url="http://localhost:8080")

async def chat_flow(agent_id: str):
    session = await client.create_auth_session(
        email="user@example.com",
        password="secret",
    )
    user_token = session["access_token"]
    principal = await client.validate_access_token(auth_token=user_token)
    user_id = principal["user_id"]

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
        "user_id": user_id,
        "chat_id": session_id,
        "message_id": "m_001",
        "role": "user",
        "content": {"text": "Hello!"},
        "telemetry_data": {"source": "chat.app"},
    }, auth_token=user_token)

    # 3. Update session status/title if needed
    await client.update_chat_session(
        chat_id=session_id,
        agent_id=agent_id,
        user_id=user_id,
        status="active",
        auth_token=user_token,
    )

    await client.refresh_auth_session()
```

## API Surface

### Chat Operations

- `listChatSessions()` / `list_chat_sessions()` - List chat sessions for a user
- `listChatMessages()` / `list_chat_messages()` - List messages in a chat session
- `writeChatMessage()` / `write_chat_message()` - Store a chat message
- `writeChatMessageFromSimpleAgentsResult()` / `write_chat_message_from_simple_agents_result()` - Store assistant message + strict `output_data` from SimpleAgents result
- `getChatMessageOutput()` / `get_chat_message_output()` - Get persisted assistant output for a message
- `upsertChatMessageOutput()` / `upsert_chat_message_output()` - Upsert message output explicitly
- `updateChatSession()` / `update_chat_session()` - Update session title or status

### Auth

- `createAuthSession()` / `create_auth_session()` - Log in with email/password and store access token
- `validateAccessToken()` / `validate_access_token()` - Validate bearer token via `/v1/me`
- `refreshAuthSession()` / `refresh_auth_session()` - Refresh access token via cookie + CSRF session

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

- `GET /v1/chat/sessions` - List chat sessions
- `GET /v1/chat/sessions?chat_id=...` - List chat messages
- `POST /v1/chat/sessions` - Write chat message
- `PATCH /v1/chat/sessions/{chat_id}` - Update chat session
- `POST /v1/auth/sessions` - Create auth session
- `POST /v1/auth/sessions/refresh` - Refresh auth session

## License

See LICENSE file.

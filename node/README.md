# SimpleFlow Node SDK

This SDK helps Node.js remote runtime backends integrate with the SimpleFlow control plane.

## Features

- API client for auth helpers and chat session operations (`listChatSessions`, `listChatMessages`, `writeChatMessage`, `updateChatSession`).
- Message output helpers (`getChatMessageOutput`, `upsertChatMessageOutput`).
- Chat scope authorization helper for preflight checks (`authorizeChatRead`).
- Control-plane auth session helpers (`createAuthSession`, `refreshAuthSession`, `validateAccessToken`).

## Install

```bash
npm install ./node/simpleflow_sdk
```

## Minimal usage

```js
const { SimpleFlowClient } = require("simpleflow-sdk")

const client = new SimpleFlowClient({
  baseUrl: "https://api.simpleflow.example",
})

const session = await client.createAuthSession({ email: "user@example.com", password: "secret" })
const userToken = session.access_token
const principal = await client.validateAccessToken({ authToken: userToken })

await client.writeChatMessage({
  agent_id: "agent_1",
  user_id: principal.user_id,
  chat_id: "chat_1",
  message_id: "m_1",
  role: "user",
  content: { text: "Hello" },
  telemetry_data: { source: "web" },
}, { authToken: userToken })

await client.writeChatMessageFromSimpleAgentsResult({
  agentId: "agent_1",
  userId: principal.user_id,
  chatId: "chat_1",
  messageId: "m_assistant_1",
  workflowResult: res,
  authToken: userToken,
})

// SDK enforces strict top-level payload keys for writeChatMessage,
// and output_data is only accepted when role is "assistant".

// For admin/super_admin callers, userId can be omitted when listing sessions/messages.
const page = await client.listChatSessionsPage({
  agentId: "agent_1",
  page: 1,
  limit: 20,
  authToken: userToken,
})
```

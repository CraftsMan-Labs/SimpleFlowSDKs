# SimpleFlow Node SDK

This SDK helps Node.js remote runtime backends integrate with the SimpleFlow control plane.

## Features

- API client for auth helpers and chat session operations (`listChatSessions`, `listChatMessages`, `writeChatMessage`, `updateChatSession`).
- Chat scope authorization helper for preflight checks (`authorizeChatRead`).

## Install

```bash
npm install ./node/simpleflow_sdk
```

## Minimal usage

```js
const { SimpleFlowClient } = require("simpleflow-sdk")

const client = new SimpleFlowClient({
  baseUrl: "https://api.simpleflow.example",
  apiToken: "user-jwt",
})

await client.writeChatMessage({
  agent_id: "agent_1",
  user_id: "user_1",
  chat_id: "chat_1",
  message_id: "m_1",
  role: "user",
  content: { text: "Hello" },
  telemetry_data: { source: "web" },
})

// For admin/super_admin callers, userId can be omitted when listing sessions/messages.
const page = await client.listChatSessionsPage({
  agentId: "agent_1",
  page: 1,
  limit: 20,
})
```

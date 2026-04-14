# Node SDK

Package: `simpleflow-sdk`

TypeScript users get bundled declarations via `index.d.ts`.

## Key APIs

- `listChatSessions(...)`
- `listChatMessages(...)`
- `writeChatMessage(...)`
- `writeChatMessageFromSimpleAgentsResult(...)`
- `getChatMessageOutput(...)`
- `upsertChatMessageOutput(...)`
- `updateChatSession(...)`
- `authorizeChatRead(...)`
- `createAuthSession(...)`
- `refreshAuthSession(...)`
- `validateAccessToken(...)`

## Install

```bash
npm install simpleflow-sdk
```

## Minimal example

```js
const { SimpleFlowClient } = require("simpleflow-sdk")

const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL,
})

const session = await client.createAuthSession({
  email: "user@example.com",
  password: "secret",
})
const userToken = session.access_token

const principal = await client.validateAccessToken({ authToken: userToken })

await client.writeChatMessage({
  agent_id: "agent_support_v1",
  user_id: principal.user_id,
  chat_id: "chat_123",
  message_id: "m_123",
  role: "user",
  content: { text: "hello" },
  telemetry_data: { source: "node-sdk-docs" },
}, { authToken: userToken })

await client.writeChatMessageFromSimpleAgentsResult({
  agentId: "agent_support_v1",
  userId: principal.user_id,
  chatId: "chat_123",
  messageId: "m_assistant_123",
  workflowResult: res,
  authToken: userToken,
})

const output = await client.getChatMessageOutput({
  messageId: "m_assistant_123",
  agentId: "agent_support_v1",
  chatId: "chat_123",
  userId: principal.user_id,
  authToken: userToken,
})
```

## TypeScript example

```ts
import { SimpleFlowClient } from "simpleflow-sdk"

const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL!,
  apiToken: process.env.SIMPLEFLOW_API_TOKEN!,
})

await client.writeChatMessage({
  agent_id: process.env.SIMPLEFLOW_AGENT_ID!,
  user_id: process.env.SIMPLEFLOW_USER_ID!,
  chat_id: "chat_123",
  message_id: "m_ts_demo",
  role: "user",
  content: { text: "hello" },
  telemetry_data: { source: "ts-sdk-docs" },
})
```

## Integration guide

- See full auth + telemetry + chat + workflow setup: [Node Integration](/sdk-node-integration)

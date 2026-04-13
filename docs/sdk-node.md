# Node SDK

Package: `simpleflow-sdk`

## Key APIs

- `listChatSessions(...)`
- `listChatMessages(...)`
- `writeChatMessage(...)`
- `updateChatSession(...)`
- `authorizeChatRead(...)`

## Install

```bash
npm install simpleflow-sdk
```

## Minimal example

```js
const { SimpleFlowClient } = require("simpleflow-sdk")

const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL,
  apiToken: process.env.SIMPLEFLOW_API_TOKEN,
})

await client.writeChatMessage({
  agent_id: "agent_support_v1",
  user_id: "user_123",
  chat_id: "chat_123",
  message_id: "m_123",
  role: "user",
  content: { text: "hello" },
  telemetry_data: { source: "node-sdk-docs" },
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

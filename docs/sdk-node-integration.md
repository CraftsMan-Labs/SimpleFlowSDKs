# Node SDK Integration Guide

This page shows the end-to-end integration flow for auth, telemetry, chat, and running workflows with SimpleAgents.

Shared auth and env model: [SDK Integration Common Guide](/sdk-integration-common)

## Runtime connect

```js
const { SimpleFlowClient } = require("simpleflow-sdk")

const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL,
  apiToken: process.env.SIMPLEFLOW_API_TOKEN,
  oauthClientId: process.env.MACHINE_CLIENT_ID,
  oauthClientSecret: process.env.MACHINE_CLIENT_SECRET,
  runtimeRegisterPath: "/v1/runtime/connect",
})

await client.registerRuntime({
  agent_id: process.env.SIMPLEFLOW_AGENT_ID,
  agent_version: process.env.SIMPLEFLOW_AGENT_VERSION,
  endpoint_url: process.env.RUNTIME_ENDPOINT_URL,
  auth_mode: "jwt",
  capabilities: ["chat", "webhook", "queue"],
  runtime_id: process.env.SIMPLEFLOW_RUNTIME_ID,
})
```

## Telemetry (workflow result)

```js
await client.writeEventFromWorkflowResult({
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  workflowResult,
})
```

## Telemetry (spans)

```js
const telemetry = client.withTelemetry({ mode: "simpleflow", sampleRate: 1.0 })
await telemetry.emitSpan({
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  runId: "run_123",
  traceId: "trace_123",
  span: { name: "llm.call", start_time_ms: 1000, end_time_ms: 1450 },
})
```

## Chat entrypoint (`/api/v1/chat`)

```js
const response = await fetch(`${process.env.SIMPLEFLOW_BASE_URL}/api/v1/chat`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.SIMPLEFLOW_API_KEY_OR_USER_TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    agent_id: process.env.SIMPLEFLOW_AGENT_ID,
    agent_version: process.env.SIMPLEFLOW_AGENT_VERSION,
    message: "hello",
  }),
})

const data = await response.json()
```

## Chat sessions (SDK)

```js
await client.writeChatMessage({
  agent_id: process.env.SIMPLEFLOW_AGENT_ID,
  chat_id: "chat_123",
  user_id: "user_123",
  message_id: "m_123",
  role: "user",
  content: { text: "hello" },
  telemetry_data: { source: "web" },
}, { authToken: process.env.SIMPLEFLOW_USER_BEARER })

const messages = await client.listChatMessages({
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  chatId: "chat_123",
  userId: "user_123",
  authToken: process.env.SIMPLEFLOW_USER_BEARER,
})

await client.updateChatSession({
  chatId: "chat_123",
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  userId: "user_123",
  status: "active",
  authToken: process.env.SIMPLEFLOW_USER_BEARER,
})
```

## Run workflows with SimpleAgents + send telemetry

```js
const { Client } = require("@craftsman-labs/simple-agents-napi")

const agents = new Client(process.env.WORKFLOW_PROVIDER || "openai")
const workflowResult = agents.runWorkflowYaml(
  process.env.WORKFLOW_PATH,
  { email_text: "hello" },
)

await client.writeEventFromWorkflowResult({
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  workflowResult,
})
```

## Minimal env

Use the shared list in [SDK Integration Common Guide](/sdk-integration-common#shared-env-variables).

Node-specific reminder:

- `SIMPLEFLOW_API_KEY_OR_USER_TOKEN` for direct `/api/v1/chat` calls.

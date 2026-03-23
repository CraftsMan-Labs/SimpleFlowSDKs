# Node SDK Integration Guide

This page shows the end-to-end integration flow for auth, telemetry, chat, and running workflows with SimpleAgents.

## Auth overview

- Machine auth (runtime connect + runtime writes): use a machine access token from `client_id` + `client_secret` (`/v1/oauth/token`).
- User auth (runtime invoke): user bearer token hits `/v1/runtime/invoke`; control plane forwards it to your runtime.
- Chat entrypoint (`/api/v1/chat`): accepts **API key** (`agk_*`) or **user bearer**. `agent_id` is required in the body.

## Runtime connect

```js
const { SimpleFlowClient } = require("simpleflow-sdk")

const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL,
  apiToken: process.env.SIMPLEFLOW_API_TOKEN,
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

## Chat history (SDK)

```js
const created = await client.createChatHistoryMessage(
  {
    agent_id: process.env.SIMPLEFLOW_AGENT_ID,
    chat_id: "chat_123",
    user_id: "user_123",
    role: "user",
    content: { text: "hello" },
    metadata: { source: "web" },
  },
  { authToken: process.env.SIMPLEFLOW_USER_BEARER },
)

const messages = await client.listChatHistoryMessages({
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  chatId: "chat_123",
  userId: "user_123",
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

- `SIMPLEFLOW_BASE_URL`
- `SIMPLEFLOW_API_TOKEN`
- `SIMPLEFLOW_AGENT_ID`
- `SIMPLEFLOW_AGENT_VERSION`
- `SIMPLEFLOW_RUNTIME_ID`
- `SIMPLEFLOW_ORGANIZATION_ID`
- `RUNTIME_ENDPOINT_URL`
- `WORKFLOW_PATH`

# Quick Start

This guide takes you from SDK install to your first runtime telemetry write.

## 1) Install an SDK

Node:

```bash
npm install simpleflow-sdk
```

Python:

```bash
pip install simpleflow-sdk
```

Go:

```bash
go get github.com/craftsman-labs/simpleflow/sdk/go/simpleflow
```

## 2) Create a client

```js
const { SimpleFlowClient } = require("simpleflow-sdk")

const client = new SimpleFlowClient({
  baseUrl: "https://api.simpleflow.example",
  apiToken: process.env.SIMPLEFLOW_API_TOKEN,
})
```

## 3) Emit an event

```js
await client.writeEvent({
  event_type: "runtime.invoke.accepted",
  agent_id: "agent_support_v1",
  organization_id: "org_123",
  user_id: "user_123",
  run_id: "run_123",
  conversation_id: "chat_123",
  request_id: "req_123",
  payload: { source: "quickstart" },
})
```

## 4) Verify in control plane

- Confirm the event appears in runtime writes.
- Confirm analytics totals move for token and event counts.

Next: wire workflow output directly with [Agent Integration](/agent-integration).

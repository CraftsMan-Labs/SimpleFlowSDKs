# Node SDK

Package: `simpleflow-sdk`

## Key APIs

- `writeEvent(...)`
- `writeChatMessage(...)`
- `publishQueueContract(...)`
- `writeEventFromWorkflowResult(...)`
- `writeChatMessageFromWorkflowResult(...)`
- `withTelemetry(...).emitSpan(...)`

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

await client.writeEvent({
  event_type: "runtime.workflow.completed",
  agent_id: "agent_support_v1",
  organization_id: "org_123",
  user_id: "user_123",
  run_id: "run_123",
  payload: { source: "node-sdk-docs" },
})
```

## Integration guide

- See full auth + telemetry + chat + workflow setup: [Node Integration](/sdk-node-integration)

# SimpleFlow Node SDK (Remote Runtime)

This SDK helps Node.js remote runtime backends integrate with the SimpleFlow control plane.

## Features

- Runtime API client for invoke and runtime writes (`writeEvent`, `writeChatMessage`, `publishQueueContract`).
- Runtime lifecycle helpers (`registerRuntime`, `listRuntimeRegistrations`, `activate/deactivate/validate`, `ensureRuntimeRegistrationActive`).
- Workflow-result bridge (`writeEventFromWorkflowResult`) that emits canonical `telemetry-envelope.v1` payloads.
- Telemetry bridge with `simpleflow` and `otlp` modes.
- Chat history list/create/update helpers.

## Install

```bash
npm install ./node/simpleflow_sdk
```

## Minimal usage

```js
const { SimpleFlowClient } = require("@simpleflow/sdk")

const client = new SimpleFlowClient({
  baseUrl: "https://api.simpleflow.example",
  apiToken: "runtime-token",
})

await client.writeEvent({
  event_type: "runtime.invoke.accepted",
  agent_id: "agent-1",
  run_id: "run_123",
  payload: { status: "accepted" },
})
```

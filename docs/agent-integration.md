# Agent Integration

This page shows how to connect SimpleAgents YAML workflow execution to SimpleFlow SDK telemetry and chat writes.

## Goal

After each workflow run, write:

- a canonical runtime event via `writeEventFromWorkflowResult(...)`
- optionally, a chat message via `writeChatMessageFromWorkflowResult(...)`

## Required identity mapping

Always map these IDs from your app context:

- `organization_id`
- `agent_id`
- `user_id`
- `conversation_id`
- `request_id`
- `run_id`

This is what lets SimpleFlow aggregate analytics and chat history per org/user/conversation/day.

## Works with local SimpleAgents repo

If your SimpleAgents project is at:

- `/Users/rishub/Desktop/projects/enterprise/craftsmanlabs/SimpleAgents`

the integration flow is the same:

1. Parse and execute YAML workflow plan in SimpleAgents.
2. Capture `workflowResult` (`events`, `metadata.trace`, `nerdstats`, timings).
3. Bridge that result into canonical telemetry-envelope payload with `writeEventFromWorkflowResult(...)`.

## Node example (SimpleAgents + SimpleFlow SDK)

```js
const { Client: SimpleAgentsClient } = require("simple-agents-node")
const { SimpleFlowClient } = require("simpleflow-sdk")

const agents = new SimpleAgentsClient(process.env.SIMPLE_AGENTS_PROVIDER || "openai")
const simpleflow = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL,
  apiToken: process.env.SIMPLEFLOW_API_TOKEN,
})

const workflowResult = agents.runWorkflowYamlWithEvents(
  "examples/simpleflow-hr-agent/workflows/email-chat-draft-or-clarify.yaml",
  {
    input: {
      messages: [{ role: "user", content: "Draft a follow-up HR email" }],
    },
  },
  {
    trace: {
      tenant: {
        organization_id: process.env.SIMPLEFLOW_ORGANIZATION_ID,
        user_id: process.env.SIMPLEFLOW_USER_ID,
        conversation_id: "chat_local_demo",
        request_id: "req_local_demo",
        run_id: "run_local_demo",
      },
    },
  }
)

await simpleflow.writeEventFromWorkflowResult({
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  organizationId: process.env.SIMPLEFLOW_ORGANIZATION_ID,
  userId: process.env.SIMPLEFLOW_USER_ID,
  workflowResult,
  eventType: "runtime.workflow.completed",
})
```

## Optional: bridge workflow result to runtime chat messages

```js
await simpleflow.writeChatMessageFromWorkflowResult({
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  organizationId: process.env.SIMPLEFLOW_ORGANIZATION_ID,
  runId: "run_local_demo",
  role: "assistant",
  workflowResult,
  chatId: "chat_local_demo",
  messageId: "msg_local_demo",
  traceId: "trace_local_demo",
})
```

## Code layout for this integration

- `examples/simpleflow-hr-agent/scripts/sync-workflow.js` - syncs YAML workflow file from template location into local example.
- `examples/simpleflow-hr-agent/scripts/run-local-agent.js` - parses/runs YAML plan with SimpleAgents and sends telemetry with `writeEventFromWorkflowResult(...)`.
- `examples/simpleflow-hr-agent/scripts/register-runtime.js` - registers runtime endpoint in control plane.
- `examples/simpleflow-hr-agent/scripts/invoke-control-plane.js` - validates `POST /v1/runtime/invoke` end-to-end.

## Streaming and thinking telemetry

When running Node chat history examples with thinking enabled, preserve raw stream context:

```bash
SIMPLE_AGENTS_WORKFLOW_STREAM_INCLUDE_RAW=1 make run-node-chat-history
```

Then bridge final result to SimpleFlow via `writeEventFromWorkflowResult(...)` so `nerdstats` and usage summaries remain queryable.

## Want full from-zero setup?

- [Zero to Control Plane](/agent-zero-to-control-plane)
- runnable reference project: `examples/simpleflow-hr-agent`

# Agent Integration

This page shows how to connect a SimpleAgents workflow execution to SimpleFlow SDK telemetry writes.

## Goal

After each workflow turn, write:

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

This enables chat history tracing and analytics by user/conversation/day.

## Node example (SimpleAgents + SimpleFlow SDK)

```js
const { Client: SimpleAgentsClient } = require("simple-agents-node")
const { SimpleFlowClient } = require("simpleflow-sdk")

const agents = new SimpleAgentsClient("openai")
const simpleflow = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL,
  apiToken: process.env.SIMPLEFLOW_API_TOKEN,
})

const workflowResult = agents.runWorkflowYamlWithEvents(
  "examples/workflow_email/email-chat-draft-or-clarify.yaml",
  { input: "Draft a follow-up email" },
  {
    trace: {
      tenant: {
        organization_id: "org_123",
        user_id: "user_123",
        conversation_id: "chat_123",
        request_id: "req_123",
        run_id: "run_123",
      },
    },
  }
)

await simpleflow.writeEventFromWorkflowResult({
  agentId: "agent_support_v1",
  organizationId: "org_123",
  userId: "user_123",
  workflowResult,
})
```

## Streaming and thinking telemetry

When running Node chat history examples with thinking enabled, preserve raw stream context:

```bash
SIMPLE_AGENTS_WORKFLOW_STREAM_INCLUDE_RAW=1 make run-node-chat-history
```

Then bridge final result to SimpleFlow via `writeEventFromWorkflowResult(...)` so `nerdstats` and usage summaries remain queryable.

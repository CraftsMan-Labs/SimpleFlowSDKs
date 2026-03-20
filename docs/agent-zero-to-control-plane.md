# Zero to Control Plane (SimpleFlow)

This guide shows a full **from-zero** setup for a local agent that registers with **SimpleFlow** control plane, runs a workflow locally, and emits canonical telemetry.

It uses the runnable example project at `examples/simpleflow-hr-agent`.

## What this guide covers

- Create and configure a local agent project.
- Sync workflow YAML from your template source.
- Register and activate runtime in SimpleFlow control plane.
- Run workflow locally and bridge telemetry with `writeEventFromWorkflowResult(...)`.
- Verify end-to-end invocation with `POST /v1/runtime/invoke`.

## Workflow used

- Template source: `/home/rishub/Desktop/projects/rishub/SimpleFlowTestTempaltes/SimpleFlowHRAgentSystem/workflows/email-chat-draft-or-clarify.yaml`
- Example copy: `examples/simpleflow-hr-agent/workflows/email-chat-draft-or-clarify.yaml`

## 1) Move to the example project

```bash
cd examples/simpleflow-hr-agent
cp .env.example .env
npm install
```

Set required values in `.env`:

- `SIMPLEFLOW_BASE_URL`
- `SIMPLEFLOW_API_TOKEN`
- `RUNTIME_ENDPOINT_URL`
- provider credentials for `simple-agents-node` (for example `CUSTOM_API_KEY`)

## 2) Keep workflow in sync

```bash
npm run sync-workflow
```

If your template location differs:

```bash
WORKFLOW_SOURCE_ROOT=/path/to/workflows npm run sync-workflow
```

## 3) Connect runtime in SimpleFlow

```bash
npm run register-runtime
```

This connects the runtime endpoint and upserts the active routing entry for your agent.

## 4) Run locally and write telemetry

```bash
npm run run-local-agent
```

This executes the workflow with local chat input and publishes a canonical event via `writeEventFromWorkflowResult(...)`.

## 5) Verify runtime invoke path

```bash
npm run invoke-control-plane
```

This sends a contract-compliant invoke request through control plane (`/v1/runtime/invoke`) and prints the runtime response.

## Reference code snippets

These snippets are the exact patterns used in `examples/simpleflow-hr-agent`.

### npm scripts

From `examples/simpleflow-hr-agent/package.json`:

```json
{
  "scripts": {
    "sync-workflow": "node scripts/sync-workflow.js",
    "register-runtime": "node scripts/register-runtime.js",
    "run-local-agent": "node scripts/run-local-agent.js",
    "invoke-control-plane": "node scripts/invoke-control-plane.js"
  }
}
```

### Connect runtime endpoint

From `examples/simpleflow-hr-agent/scripts/register-runtime.js`:

```js
const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL,
  apiToken: process.env.SIMPLEFLOW_API_TOKEN,
  runtimeRegisterPath: "/v1/runtime/connect",
})

const connectPayload = {
  agent_id: process.env.SIMPLEFLOW_AGENT_ID || "hr-agent-runtime",
  agent_version: process.env.SIMPLEFLOW_AGENT_VERSION || "v1",
  endpoint_url: process.env.RUNTIME_ENDPOINT_URL,
  auth_mode: process.env.RUNTIME_AUTH_MODE || "jwt",
  capabilities: ["chat", "webhook", "queue"],
  runtime_id: process.env.SIMPLEFLOW_RUNTIME_ID || "runtime_local_hr_agent",
}

const result = await client.registerRuntime(connectPayload)
```

### Run local workflow and emit telemetry

From `examples/simpleflow-hr-agent/scripts/run-local-agent.js`:

```js
const workflowResult = await agents.runWorkflowYamlWithEvents(
  "./workflows/email-chat-draft-or-clarify.yaml",
  { input: { messages: [{ role: "user", content: process.env.USER_MESSAGE }] } },
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
  agentId: process.env.SIMPLEFLOW_AGENT_ID || "hr-agent-runtime",
  organizationId: process.env.SIMPLEFLOW_ORGANIZATION_ID,
  userId: process.env.SIMPLEFLOW_USER_ID,
  workflowResult,
  eventType: "runtime.workflow.completed",
})
```

### Invoke runtime through control plane

From `examples/simpleflow-hr-agent/scripts/invoke-control-plane.js`:

```js
const response = await client.invoke({
  schema_version: "v1",
  run_id: "run_local_demo",
  agent_id: process.env.SIMPLEFLOW_AGENT_ID || "hr-agent-runtime",
  agent_version: process.env.SIMPLEFLOW_AGENT_VERSION || "v1",
  mode: "realtime",
  trace: { trace_id: "trace_local", span_id: "span_local", tenant_id: process.env.SIMPLEFLOW_ORGANIZATION_ID },
  input: { message: process.env.USER_MESSAGE },
  deadline_ms: 120000,
  idempotency_key: "invoke_local_demo",
})
```

### Sync workflow from template source

From `examples/simpleflow-hr-agent/scripts/sync-workflow.js`:

```js
const sourceRoot = process.env.WORKFLOW_SOURCE_ROOT || "/home/rishub/Desktop/projects/rishub/SimpleFlowTestTempaltes/SimpleFlowHRAgentSystem/workflows"
const sourceFile = path.resolve(sourceRoot, "email-chat-draft-or-clarify.yaml")
const targetFile = path.resolve(__dirname, "..", "workflows", "email-chat-draft-or-clarify.yaml")
fs.copyFileSync(sourceFile, targetFile)
```

## Optional input modes

- `USER_MESSAGE` in `.env` for single-turn runs.
- `INPUT_MESSAGES_JSON` for full multi-message context.

Example `INPUT_MESSAGES_JSON` file:

```json
[
  { "role": "user", "content": "Please draft an HR warning email for repeated late arrivals." }
]
```

## Sync contract

To keep docs and runnable sample aligned:

- Treat `examples/simpleflow-hr-agent` as source of truth for commands.
- Use `examples/simpleflow-hr-agent/scripts/sync-workflow.js` whenever template workflow changes.
- Keep this page focused on flow; keep implementation details in `examples/simpleflow-hr-agent/README.md`.

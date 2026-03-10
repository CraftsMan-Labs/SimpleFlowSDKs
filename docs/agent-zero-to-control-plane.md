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

## 3) Register runtime in SimpleFlow

```bash
npm run register-runtime
```

This calls `ensureRuntimeRegistrationActive(...)` and handles create + validate + activate lifecycle.

Expected fields in output:

- `status: "active"`
- `registration_id`

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

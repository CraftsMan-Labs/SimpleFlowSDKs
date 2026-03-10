# SimpleFlow HR Agent Example (Zero to Control Plane)

This example shows how to create an agent from scratch, register it with **SimpleFlow** control plane, run the workflow locally, and keep workflow files in sync with your template source.

## Workflow source

- Canonical source: `/home/rishub/Desktop/projects/rishub/SimpleFlowTestTempaltes/SimpleFlowHRAgentSystem/workflows/email-chat-draft-or-clarify.yaml`
- Local copy used by this example: `examples/simpleflow-hr-agent/workflows/email-chat-draft-or-clarify.yaml`

Use the sync command whenever the template workflow changes.

## 1) Install and configure

```bash
cd examples/simpleflow-hr-agent
cp .env.example .env
npm install
```

Update `.env`:

- `SIMPLEFLOW_BASE_URL`
- `SIMPLEFLOW_API_TOKEN`
- `RUNTIME_ENDPOINT_URL` (runtime URL reachable by control-plane backend)
- provider key used by `simple-agents-node` (`CUSTOM_API_KEY` or provider-specific key)

## 2) Sync workflow from template source

```bash
npm run sync-workflow
```

Optional alternate source path:

```bash
WORKFLOW_SOURCE_ROOT=/path/to/your/workflows npm run sync-workflow
```

## 3) Register runtime in SimpleFlow control plane

```bash
npm run register-runtime
```

Expected output includes:

- `status: "active"`
- `registration_id`

## 4) Run the agent locally and emit telemetry

```bash
npm run run-local-agent
```

This runs `email-chat-draft-or-clarify.yaml` with local input and writes a canonical `runtime.workflow.completed` event through `writeEventFromWorkflowResult(...)`.

## 5) Invoke through control-plane runtime API

```bash
npm run invoke-control-plane
```

This verifies runtime invocation contract end-to-end (`POST /v1/runtime/invoke`).

## Optional inputs

- Use `USER_MESSAGE` in `.env` for a quick single-turn prompt.
- Use `INPUT_MESSAGES_JSON` with a JSON array of chat messages for richer context:

```json
[
  { "role": "user", "content": "Can you draft an HR warning email for repeated late arrivals?" }
]
```

## Files

- `scripts/sync-workflow.js`: sync workflow from template repo.
- `scripts/register-runtime.js`: create/validate/activate registration.
- `scripts/run-local-agent.js`: local workflow run + telemetry write.
- `scripts/invoke-control-plane.js`: invoke runtime via control plane.

# SimpleFlow SDKs

Language SDKs for integrating remote runtimes with the SimpleFlow control plane.

If you are landing here for the first time, use the quick links below and you can be running in minutes.

## Start here

### 1) Install an SDK

```bash
# JavaScript / TypeScript
npm install simpleflow-sdk

# Python
pip install simpleflow-sdk

# Go
go get github.com/craftsman-labs/simpleflow/sdk/go/simpleflow
```

### 2) Choose auth (pick one)

- `SIMPLEFLOW_API_TOKEN` (fastest)
- `MACHINE_CLIENT_ID` + `MACHINE_CLIENT_SECRET` (OAuth client credentials)

Required base env:

```bash
export SIMPLEFLOW_BASE_URL="http://localhost:8080"
```

### 3) Set identity env

Typical runtime identity keys:

- `SIMPLEFLOW_AGENT_ID`
- `SIMPLEFLOW_AGENT_VERSION`
- `SIMPLEFLOW_ORGANIZATION_ID`
- `SIMPLEFLOW_USER_ID`
- `SIMPLEFLOW_RUNTIME_ID`
- `RUNTIME_ENDPOINT_URL`
- `SIMPLEFLOW_USER_BEARER` (only for user-scoped chat history APIs)

### 4) Copy/paste snippets by language

- JS/TS/Python/Go quickstart snippets: `docs/quickstart.md`
- Shared auth/env/flow model: `docs/sdk-integration-common.md`
- Node integration (auth, telemetry, chat, workflow): `docs/sdk-node-integration.md`
- Python integration (auth, telemetry, chat, workflow): `docs/sdk-python-integration.md`
- Go integration (auth, telemetry, chat, workflow): `docs/sdk-go-integration.md`

## Works with SimpleAgents (YAML workflow -> SimpleFlow telemetry)

This repository includes a runnable integration in `examples/simpleflow-hr-agent` that bridges SimpleAgents workflow execution to canonical SimpleFlow telemetry.

If you are developing in the local SimpleAgents repo at `/Users/rishub/Desktop/projects/enterprise/craftsmanlabs/SimpleAgents`, the integration pattern is:

1. Parse and execute a YAML workflow plan in SimpleAgents.
2. Capture `workflowResult` from the run.
3. Send canonical telemetry using `writeEventFromWorkflowResult(...)`.

Reference implementation:

- `examples/simpleflow-hr-agent/scripts/run-local-agent.js`
- `examples/simpleflow-hr-agent/scripts/sync-workflow.js`

The bridge call (same pattern as the runnable example):

```js
await simpleflow.writeEventFromWorkflowResult({
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  organizationId: process.env.SIMPLEFLOW_ORGANIZATION_ID,
  userId: process.env.SIMPLEFLOW_USER_ID,
  workflowResult,
  eventType: "runtime.workflow.completed",
})
```

## Code layout

- `node/simpleflow_sdk` - Node/JS/TS SDK package (`simpleflow-sdk`).
- `python/simpleflow_sdk` - Python SDK package (`simpleflow-sdk`).
- `go/simpleflow` - Go SDK module.
- `examples/simpleflow-hr-agent` - end-to-end sample with workflow sync, runtime register, local run, and invoke verification.
- `docs/` - VitePress docs source.

## Current API surface

- Control plane: `registerRuntime(...)`, `invoke(...)`.
- Runtime writes: `writeEvent(...)`, `writeChatMessage(...)`, `publishQueueContract(...)`.
- Chat history: `listChatHistoryMessages(...)`, `createChatHistoryMessage(...)`, `updateChatHistoryMessage(...)`.
- Workflow bridge: `writeEventFromWorkflowResult(...)`.
- Telemetry bridge: `withTelemetry(...).emitSpan(...)` with `simpleflow` and `otlp` modes.
- Canonical workflow telemetry payload: `telemetry-envelope.v1` (see `docs/telemetry-envelope-v1-spec.md`).

## Docs

- Docs home: `https://docs.simpleflow-sdk.craftsmanlabs.net`
- Quick start: `docs/quickstart.md`
- Shared integration model: `docs/sdk-integration-common.md`
- Agent integration: `docs/agent-integration.md`
- Zero to control plane: `docs/agent-zero-to-control-plane.md`
- Node/Python/Go integration pages: `docs/sdk-node-integration.md`, `docs/sdk-python-integration.md`, `docs/sdk-go-integration.md`

## Developer commands

Use the root `Makefile` for common workflows:

- `make test` runs Go, Python, and Node tests.
- `make clean` removes generated build artifacts and local dependency folders.
- `make test-node` runs Node SDK tests.
- `make lint-go` and `make fmt-go` run Go quality checks.
- `make check-publish` runs release readiness checks.
- `make check-publish-all` runs release checks plus dry-run publish checks.
- `make publish-python-dry` builds Python artifacts without uploading.
- `make publish-python` uploads Python artifacts with Doppler + `uv publish`.
- `make publish-node-dry` runs npm publish dry-run for Node SDK.
- `make publish-node` uploads Node package using env token or local npm session.
- `make publish-node-doppler` uploads Node package with Doppler + `npm publish`.
- `make publish-all` publishes both Python and Node SDK packages.
- `make version-patch` / `make version-minor` / `make version-major` bump Python + Node versions together.
- `make version-patch AUTO_GIT=1` (or minor/major/set) auto-commits, tags, and pushes the release.
- `make release-patch` / `make release-minor` / `make release-major` bump version and auto commit/tag/push in one command.
- `make publish-go-tag VERSION=vX.Y.Z` creates and pushes a Go release tag.

# SimpleFlow SDKs

Language SDKs for integrating remote runtimes with the SimpleFlow control plane.

If you are landing here for the first time, you can copy/paste the examples below and start writing telemetry, chat, auth, and workflow bridge events immediately.

## Start in 5 minutes

### 1) Install an SDK

JavaScript (Node):

```bash
npm install simpleflow-sdk
```

TypeScript (Node + TS):

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

### 2) Choose auth (pick one)

Option A - API token (fastest):

```bash
export SIMPLEFLOW_BASE_URL="http://localhost:8080"
export SIMPLEFLOW_API_TOKEN="<machine_runtime_token>"
```

Option B - machine client credentials (`MACHINE_CLIENT_ID` + `MACHINE_CLIENT_SECRET`):

```bash
export SIMPLEFLOW_BASE_URL="http://localhost:8080"
export MACHINE_CLIENT_ID="<machine_client_id>"
export MACHINE_CLIENT_SECRET="<machine_client_secret>"
```

For Go, exchange machine credentials for an access token first, then set `SIMPLEFLOW_API_TOKEN`:

```bash
export SIMPLEFLOW_API_TOKEN="$(curl -sS -X POST "$SIMPLEFLOW_BASE_URL/v1/oauth/token" \
  -H "Content-Type: application/json" \
  -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"$MACHINE_CLIENT_ID\",\"client_secret\":\"$MACHINE_CLIENT_SECRET\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
```

### 3) Set identity env

Common runtime + telemetry env used in examples:

- `SIMPLEFLOW_AGENT_ID`
- `SIMPLEFLOW_AGENT_VERSION`
- `SIMPLEFLOW_ORGANIZATION_ID`
- `SIMPLEFLOW_USER_ID`
- `SIMPLEFLOW_RUNTIME_ID`
- `RUNTIME_ENDPOINT_URL`
- `SIMPLEFLOW_USER_BEARER` (for user-scoped chat history APIs)

Copy/paste identity env template:

```bash
export SIMPLEFLOW_AGENT_ID="hr-agent-runtime"
export SIMPLEFLOW_AGENT_VERSION="v1"
export SIMPLEFLOW_ORGANIZATION_ID="org_local_demo"
export SIMPLEFLOW_USER_ID="user_local_demo"
export SIMPLEFLOW_RUNTIME_ID="runtime_local_hr_agent"
export RUNTIME_ENDPOINT_URL="http://localhost:8092"
export SIMPLEFLOW_USER_BEARER="<user_bearer_token>"
```

### 4) Copy/paste quick usage

#### JavaScript (Node)

```js
const crypto = require("node:crypto")
const { SimpleFlowClient } = require("simpleflow-sdk")

const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL,
  apiToken: process.env.SIMPLEFLOW_API_TOKEN,
  oauthClientId: process.env.MACHINE_CLIENT_ID,
  oauthClientSecret: process.env.MACHINE_CLIENT_SECRET,
})

await client.writeEvent({
  event_type: "runtime.invoke.accepted",
  agent_id: process.env.SIMPLEFLOW_AGENT_ID,
  organization_id: process.env.SIMPLEFLOW_ORGANIZATION_ID,
  user_id: process.env.SIMPLEFLOW_USER_ID,
  run_id: `run_${crypto.randomUUID().slice(0, 8)}`,
  payload: { source: "js-quickstart" },
})

await client.writeChatMessage({
  agent_id: process.env.SIMPLEFLOW_AGENT_ID,
  organization_id: process.env.SIMPLEFLOW_ORGANIZATION_ID,
  run_id: `run_${crypto.randomUUID().slice(0, 8)}`,
  chat_id: "chat_local_demo",
  role: "assistant",
  content: { text: "Hello from JS SDK" },
})

const telemetry = client.withTelemetry({ mode: "simpleflow", sampleRate: 1.0 })
await telemetry.emitSpan({
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  runId: "run_local_demo",
  traceId: "trace_local_demo",
  span: { name: "llm.call", start_time_ms: 1000, end_time_ms: 1300 },
})

const messages = await client.listChatHistoryMessages({
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  chatId: "chat_local_demo",
  userId: process.env.SIMPLEFLOW_USER_ID,
  authToken: process.env.SIMPLEFLOW_USER_BEARER,
})

console.log("chat_history_count", messages.length)
```

#### TypeScript

```ts
import { SimpleFlowClient } from "simpleflow-sdk"

const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL!,
  apiToken: process.env.SIMPLEFLOW_API_TOKEN,
  oauthClientId: process.env.MACHINE_CLIENT_ID,
  oauthClientSecret: process.env.MACHINE_CLIENT_SECRET,
})

await client.writeEvent({
  event_type: "runtime.workflow.completed",
  agent_id: process.env.SIMPLEFLOW_AGENT_ID!,
  organization_id: process.env.SIMPLEFLOW_ORGANIZATION_ID!,
  user_id: process.env.SIMPLEFLOW_USER_ID!,
  run_id: "run_ts_demo",
  conversation_id: "chat_ts_demo",
  request_id: "req_ts_demo",
  payload: { source: "ts-quickstart" },
})
```

#### Python

```python
import os
from simpleflow_sdk import SimpleFlowClient

client = SimpleFlowClient(
    base_url=os.environ["SIMPLEFLOW_BASE_URL"],
    api_token=os.getenv("SIMPLEFLOW_API_TOKEN"),
    oauth_client_id=os.getenv("MACHINE_CLIENT_ID"),
    oauth_client_secret=os.getenv("MACHINE_CLIENT_SECRET"),
)

client.write_event(
    {
        "event_type": "runtime.workflow.completed",
        "agent_id": os.environ["SIMPLEFLOW_AGENT_ID"],
        "organization_id": os.environ["SIMPLEFLOW_ORGANIZATION_ID"],
        "user_id": os.environ["SIMPLEFLOW_USER_ID"],
        "run_id": "run_py_demo",
        "payload": {"source": "python-quickstart"},
    }
)

client.write_chat_message(
    {
        "agent_id": os.environ["SIMPLEFLOW_AGENT_ID"],
        "organization_id": os.environ["SIMPLEFLOW_ORGANIZATION_ID"],
        "run_id": "run_py_demo",
        "chat_id": "chat_py_demo",
        "role": "assistant",
        "content": {"text": "Hello from Python SDK"},
    }
)

telemetry = client.with_telemetry(mode="simpleflow", sample_rate=1.0)
telemetry.emit_span(
    agent_id=os.environ["SIMPLEFLOW_AGENT_ID"],
    run_id="run_py_demo",
    trace_id="trace_py_demo",
    span={"name": "llm.call", "start_time_ms": 1000, "end_time_ms": 1200},
)
```

#### Go

```go
package main

import (
    "context"
    "log"
    "os"

    "github.com/craftsman-labs/simpleflow/sdk/go/simpleflow"
)

func main() {
    ctx := context.Background()

    client, err := simpleflow.NewClient(simpleflow.ClientConfig{
        BaseURL:  os.Getenv("SIMPLEFLOW_BASE_URL"),
        APIToken: os.Getenv("SIMPLEFLOW_API_TOKEN"),
    })
    if err != nil {
        log.Fatal(err)
    }

    err = client.WriteEvent(ctx, simpleflow.RuntimeEvent{
        Type:           "runtime.workflow.completed",
        AgentID:        os.Getenv("SIMPLEFLOW_AGENT_ID"),
        OrganizationID: os.Getenv("SIMPLEFLOW_ORGANIZATION_ID"),
        UserID:         os.Getenv("SIMPLEFLOW_USER_ID"),
        RunID:          "run_go_demo",
        Payload:        map[string]any{"source": "go-quickstart"},
    })
    if err != nil {
        log.Fatal(err)
    }
}
```

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
- Agent integration: `docs/agent-integration.md`
- Zero to control plane: `docs/agent-zero-to-control-plane.md`
- Node/Python/Go integration pages: `docs/sdk-node-integration.md`, `docs/sdk-python-integration.md`, `docs/sdk-go-integration.md`

## Developer commands

Use the root `Makefile` for common workflows:

- `make test` runs Go, Python, and Node tests.
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

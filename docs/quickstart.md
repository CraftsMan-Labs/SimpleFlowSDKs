# Quick Start

This page is optimized for copy/paste onboarding. Pick a language, set env, run one snippet.

## 1) Install

JavaScript:

```bash
npm install simpleflow-sdk
```

TypeScript:

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

## 2) Choose auth (pick one)

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

## 3) Identity env

Recommended for telemetry + chat identity:

- `SIMPLEFLOW_AGENT_ID`
- `SIMPLEFLOW_AGENT_VERSION`
- `SIMPLEFLOW_ORGANIZATION_ID`
- `SIMPLEFLOW_USER_ID`
- `SIMPLEFLOW_RUNTIME_ID`
- `RUNTIME_ENDPOINT_URL`
- `SIMPLEFLOW_USER_BEARER` (only for user-scoped chat history APIs)
- or `SIMPLEFLOW_USER_EMAIL` + `SIMPLEFLOW_USER_PASSWORD` for control-plane session login

Copy/paste:

```bash
export SIMPLEFLOW_AGENT_ID="hr-agent-runtime"
export SIMPLEFLOW_AGENT_VERSION="v1"
export SIMPLEFLOW_ORGANIZATION_ID="org_local_demo"
export SIMPLEFLOW_USER_ID="user_local_demo"
export SIMPLEFLOW_RUNTIME_ID="runtime_local_hr_agent"
export RUNTIME_ENDPOINT_URL="http://localhost:8092"
export SIMPLEFLOW_USER_BEARER="<user_bearer_token>"
export SIMPLEFLOW_USER_EMAIL="user@example.com"
export SIMPLEFLOW_USER_PASSWORD="secret"
```

## 4) JavaScript (Node): telemetry + chat + history

```js
const crypto = require("node:crypto")
const { SimpleFlowClient } = require("simpleflow-sdk")

const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL,
  apiToken: process.env.SIMPLEFLOW_API_TOKEN,
  oauthClientId: process.env.MACHINE_CLIENT_ID,
  oauthClientSecret: process.env.MACHINE_CLIENT_SECRET,
})

let userToken = process.env.SIMPLEFLOW_USER_BEARER || ""
if (!userToken && process.env.SIMPLEFLOW_USER_EMAIL && process.env.SIMPLEFLOW_USER_PASSWORD) {
  const session = await client.createAuthSession({
    email: process.env.SIMPLEFLOW_USER_EMAIL,
    password: process.env.SIMPLEFLOW_USER_PASSWORD,
  })
  userToken = session.access_token
}

const messageId = `m_${crypto.randomUUID().slice(0, 8)}`

await client.writeChatMessage({
  agent_id: process.env.SIMPLEFLOW_AGENT_ID,
  user_id: process.env.SIMPLEFLOW_USER_ID,
  chat_id: "chat_local_demo",
  message_id: messageId,
  role: "assistant",
  content: { text: "Hello from JS SDK" },
  telemetry_data: { source: "quickstart-js" },
}, { authToken: userToken })

const messages = await client.listChatMessages({
  agentId: process.env.SIMPLEFLOW_AGENT_ID,
  chatId: "chat_local_demo",
  userId: process.env.SIMPLEFLOW_USER_ID,
  authToken: userToken,
})

console.log("history_count", messages.length)
```

## 5) TypeScript: chat write

```ts
import { SimpleFlowClient } from "simpleflow-sdk"

const client = new SimpleFlowClient({
  baseUrl: process.env.SIMPLEFLOW_BASE_URL!,
  apiToken: process.env.SIMPLEFLOW_API_TOKEN,
  oauthClientId: process.env.MACHINE_CLIENT_ID,
  oauthClientSecret: process.env.MACHINE_CLIENT_SECRET,
})

const session = await client.createAuthSession({
  email: process.env.SIMPLEFLOW_USER_EMAIL!,
  password: process.env.SIMPLEFLOW_USER_PASSWORD!,
})
const userToken = session.access_token

const principal = await client.validateAccessToken({ authToken: userToken })

await client.writeChatMessage({
  agent_id: process.env.SIMPLEFLOW_AGENT_ID!,
  user_id: principal.user_id,
  chat_id: "chat_ts_demo",
  message_id: "m_ts_demo",
  role: "assistant",
  content: { text: "Hello from TS SDK" },
  telemetry_data: { source: "quickstart-ts" },
}, { authToken: userToken })

const res = {
  workflow_id: "wf_demo",
  terminal_output: { label: "finance/invoice", reason: "demo" },
}

await client.writeChatMessageFromSimpleAgentsResult({
  agentId: process.env.SIMPLEFLOW_AGENT_ID!,
  userId: principal.user_id,
  chatId: "chat_ts_demo",
  messageId: "m_ts_assistant",
  workflowResult: res,
  authToken: userToken,
})
```

## 6) Python: chat

```python
import os
from simpleflow_sdk import SimpleFlowClient

client = SimpleFlowClient(
    base_url=os.environ["SIMPLEFLOW_BASE_URL"],
    api_token=os.getenv("SIMPLEFLOW_API_TOKEN"),
    oauth_client_id=os.getenv("MACHINE_CLIENT_ID"),
    oauth_client_secret=os.getenv("MACHINE_CLIENT_SECRET"),
)

user_token = os.getenv("SIMPLEFLOW_USER_BEARER", "")
if not user_token and os.getenv("SIMPLEFLOW_USER_EMAIL") and os.getenv("SIMPLEFLOW_USER_PASSWORD"):
    session = await client.create_auth_session(
        email=os.environ["SIMPLEFLOW_USER_EMAIL"],
        password=os.environ["SIMPLEFLOW_USER_PASSWORD"],
    )
    user_token = session["access_token"]

await client.write_chat_message(
    {
        "agent_id": os.environ["SIMPLEFLOW_AGENT_ID"],
        "user_id": os.environ["SIMPLEFLOW_USER_ID"],
        "chat_id": "chat_py_demo",
        "message_id": "m_py_demo",
        "role": "assistant",
        "content": {"text": "Hello from Python SDK"},
        "telemetry_data": {"source": "quickstart-python"},
    },
    auth_token=user_token,
)
```

## 7) Go: telemetry

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
        Payload:        map[string]any{"source": "quickstart-go"},
    })
    if err != nil {
        log.Fatal(err)
    }
}
```

## 8) Verify in control plane

- Confirm your event appears under runtime writes.
- Confirm chat writes/history are visible for your chat ID.
- Confirm telemetry span/event metrics move.

Next: connect SimpleAgents YAML workflow output directly with [Agent Integration](/agent-integration).

# SimpleFlow Go SDK (Remote Runtime)

This SDK helps remote runtime backends integrate with the SimpleFlow control plane.

## Features

- Typed invoke request/result and error envelope contracts.
- Control-plane API client for runtime event, chat message, and queue contract writes.
- Invoke token verifier using JWKS-based signature validation.

## Install

```bash
go get github.com/craftsman-labs/simpleflow/sdk/go/simpleflow
```

## Minimal usage

```go
client, err := simpleflow.NewClient(simpleflow.ClientConfig{
    BaseURL:  "https://api.simpleflow.example",
    APIToken: "runtime-service-token",
})
if err != nil {
    panic(err)
}

err = client.ReportRuntimeEvent(ctx, simpleflow.RuntimeEvent{
    Type:         "runtime.invoke.accepted",
    AgentID:      "agent-1",
    AgentVersion: "v1",
    RunID:        "run_123",
})
```

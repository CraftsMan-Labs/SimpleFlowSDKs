# SimpleFlow Go SDK (Remote Runtime)

This SDK helps remote runtime backends integrate with the SimpleFlow control plane.

## Features

- Typed invoke request/result and error envelope contracts.
- Control-plane API client for runtime registration and invoke.
- Runtime API client for event, chat message, and queue contract writes.
- Chat history APIs for list/create/update by `agent_id` + `chat_id` + `user_id`.
- Invoke token verifier using JWKS-based signature validation.
- Telemetry bridge with `simpleflow` and `otlp` modes.

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

err = client.WriteEvent(ctx, simpleflow.RuntimeEvent{
    Type:         "runtime.invoke.accepted",
    AgentID:      "agent-1",
    RunID:        "run_123",
})

telemetry, err := client.WithTelemetry(simpleflow.TelemetryConfig{Mode: simpleflow.TelemetryModeSimpleFlow})
if err != nil {
    panic(err)
}
err = telemetry.EmitSpan(ctx, simpleflow.EmitSpanInput{
    AgentID: "agent-1",
    RunID:   "run_123",
    TraceID: "trace_123",
    Span: simpleflow.TelemetrySpan{
        Name:        "llm.call",
        StartTimeMS: 1000,
        EndTimeMS:   1200,
    },
})
```

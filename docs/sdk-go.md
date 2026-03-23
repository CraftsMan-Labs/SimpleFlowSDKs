# Go SDK

Module: `github.com/craftsman-labs/simpleflow/sdk/go/simpleflow`

## Key APIs

- `WriteEvent(...)`
- `WriteChatMessage(...)`
- `PublishQueueContract(...)`
- `WriteEventFromWorkflowResult(...)`
- `WriteChatMessageFromWorkflowResult(...)`
- `WithTelemetry(...).EmitSpan(...)`

## Install

```bash
go get github.com/craftsman-labs/simpleflow/sdk/go/simpleflow
```

## Minimal example

```go
client, _ := simpleflow.NewClient(simpleflow.Config{
    BaseURL:  "https://api.simpleflow.example",
    APIToken: "<token>",
})

_ = client.WriteEvent(ctx, simpleflow.RuntimeEvent{
    Type:           "runtime.workflow.completed",
    AgentID:        "agent_support_v1",
    OrganizationID: "org_123",
    UserID:         "user_123",
    RunID:          "run_123",
    Payload:        map[string]any{"source": "go-sdk-docs"},
})
```

## Integration guide

- See full auth + telemetry + chat + workflow setup: [Go Integration](/sdk-go-integration)

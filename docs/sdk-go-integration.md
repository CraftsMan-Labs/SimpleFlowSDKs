# Go SDK Integration Guide

This page shows the end-to-end integration flow for auth, telemetry, chat, and running workflows with SimpleAgents.

## Auth overview

- Machine auth (runtime connect + runtime writes): use a machine access token from `client_id` + `client_secret` (`/v1/oauth/token`).
- User auth (runtime invoke): user bearer token hits `/v1/runtime/invoke`; control plane forwards it to your runtime.
- Chat entrypoint (`/api/v1/chat`): accepts **API key** (`agk_*`) or **user bearer**. `agent_id` is required in the body.

## Runtime connect

```go
client, err := simpleflow.NewClient(simpleflow.ClientConfig{
    BaseURL:             os.Getenv("SIMPLEFLOW_BASE_URL"),
    APIToken:            os.Getenv("SIMPLEFLOW_API_TOKEN"),
    RuntimeRegisterPath: "/v1/runtime/connect",
})
if err != nil {
    log.Fatal(err)
}

err = client.RegisterRuntime(ctx, simpleflow.RuntimeRegistration{
    AgentID:      os.Getenv("SIMPLEFLOW_AGENT_ID"),
    AgentVersion: os.Getenv("SIMPLEFLOW_AGENT_VERSION"),
    EndpointURL:  os.Getenv("RUNTIME_ENDPOINT_URL"),
    AuthMode:     "jwt",
    Capabilities: []string{"chat", "webhook", "queue"},
    RuntimeID:    os.Getenv("SIMPLEFLOW_RUNTIME_ID"),
})
if err != nil {
    log.Fatal(err)
}
```

## Telemetry (workflow result)

```go
err = client.WriteEventFromWorkflowResult(ctx, simpleflow.WriteEventFromWorkflowResultInput{
    AgentID:        os.Getenv("SIMPLEFLOW_AGENT_ID"),
    WorkflowResult: workflowResult,
})
```

## Telemetry (spans)

```go
telemetry, err := client.WithTelemetry(simpleflow.TelemetryConfig{Mode: simpleflow.TelemetryModeSimpleFlow})
if err != nil {
    log.Fatal(err)
}

err = telemetry.EmitSpan(ctx, simpleflow.EmitSpanInput{
    AgentID: os.Getenv("SIMPLEFLOW_AGENT_ID"),
    RunID:   "run_123",
    TraceID: "trace_123",
    Span: simpleflow.TelemetrySpan{
        Name:        "llm.call",
        StartTimeMS: 1000,
        EndTimeMS:   1450,
    },
})
```

## Chat entrypoint (`/api/v1/chat`)

```go
payload := map[string]any{
    "agent_id":      os.Getenv("SIMPLEFLOW_AGENT_ID"),
    "agent_version": os.Getenv("SIMPLEFLOW_AGENT_VERSION"),
    "message":       "hello",
}
body, _ := json.Marshal(payload)

req, _ := http.NewRequest(http.MethodPost, os.Getenv("SIMPLEFLOW_BASE_URL")+"/api/v1/chat", bytes.NewReader(body))
req.Header.Set("Authorization", "Bearer "+os.Getenv("SIMPLEFLOW_API_KEY_OR_USER_TOKEN"))
req.Header.Set("Content-Type", "application/json")

resp, err := http.DefaultClient.Do(req)
if err != nil {
    log.Fatal(err)
}
defer resp.Body.Close()
```

## Chat history (SDK)

```go
userClient, err := simpleflow.NewClient(simpleflow.ClientConfig{
    BaseURL:  os.Getenv("SIMPLEFLOW_BASE_URL"),
    APIToken: os.Getenv("SIMPLEFLOW_USER_BEARER"),
})
if err != nil {
    log.Fatal(err)
}

created, err := userClient.CreateChatHistoryMessage(ctx, simpleflow.ChatHistoryMessage{
    AgentID:  os.Getenv("SIMPLEFLOW_AGENT_ID"),
    ChatID:   "chat_123",
    UserID:   "user_123",
    Role:     "user",
    Content:  map[string]any{"text": "hello"},
    Metadata: map[string]any{"source": "web"},
})
if err != nil {
    log.Fatal(err)
}

messages, err := userClient.ListChatHistoryMessages(ctx, simpleflow.ChatHistoryListInput{
    AgentID: os.Getenv("SIMPLEFLOW_AGENT_ID"),
    ChatID:  "chat_123",
    UserID:  "user_123",
})
```

## Run workflows with SimpleAgents + send telemetry

```go
agents, err := simpleagents.NewClientFromEnv(os.Getenv("WORKFLOW_PROVIDER"))
if err != nil {
    log.Fatal(err)
}
defer agents.Close()

workflowResult, err := agents.RunWorkflowYAML(ctx, os.Getenv("WORKFLOW_PATH"), map[string]any{
    "email_text": "hello",
})
if err != nil {
    log.Fatal(err)
}

err = client.WriteEventFromWorkflowResult(ctx, simpleflow.WriteEventFromWorkflowResultInput{
    AgentID:        os.Getenv("SIMPLEFLOW_AGENT_ID"),
    WorkflowResult: workflowResult,
})
```

## Minimal env

- `SIMPLEFLOW_BASE_URL`
- `SIMPLEFLOW_API_TOKEN`
- `SIMPLEFLOW_AGENT_ID`
- `SIMPLEFLOW_AGENT_VERSION`
- `SIMPLEFLOW_RUNTIME_ID`
- `SIMPLEFLOW_ORGANIZATION_ID`
- `RUNTIME_ENDPOINT_URL`
- `WORKFLOW_PATH`

# TelemetryEnvelopeV1

This document defines the canonical telemetry payload used by SDK workflow-result bridges.

## Envelope

`payload.schema_version` MUST be `telemetry-envelope.v1`.

Top-level payload shape:

```json
{
  "schema_version": "telemetry-envelope.v1",
  "identity": {
    "organization_id": "org_123",
    "agent_id": "agent_support_v1",
    "user_id": "user_123"
  },
  "trace": {
    "trace_id": "trace_123",
    "span_id": "span_123",
    "tenant_id": "tenant_123",
    "conversation_id": "chat_123",
    "request_id": "req_123",
    "run_id": "run_123",
    "sampled": true
  },
  "workflow": {
    "workflow_id": "email-chat-draft-or-clarify",
    "terminal_node": "ask_for_scenario",
    "status": "completed",
    "total_elapsed_ms": 1234,
    "ttft_ms": 20
  },
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150,
    "reasoning_tokens": 20,
    "ttft_ms": 20,
    "total_elapsed_ms": 1234,
    "tokens_per_second": 44.6
  },
  "model_usage": [
    {
      "model": "gpt-5-mini",
      "request_count": 2,
      "prompt_tokens": 80,
      "completion_tokens": 40,
      "total_tokens": 120,
      "reasoning_tokens": 20,
      "elapsed_ms": 900
    }
  ],
  "tool_usage": [
    {
      "tool": "workflow_tools",
      "started_count": 3,
      "completed_count": 2,
      "error_count": 1
    }
  ],
  "event_counts": {
    "workflow_started": 1,
    "node_tool_start": 3,
    "workflow_completed": 1
  },
  "nerdstats": {},
  "raw": {}
}
```

## Notes

- `raw` is optional and should only be included for debug or audit use-cases.
- `nerdstats` is optional and mirrors provider-specific details from workflow execution.
- Runtime event envelope fields (`agent_id`, `organization_id`, `user_id`, `run_id`, `trace_id`, `conversation_id`, `request_id`, `sampled`) should be aligned with this payload.

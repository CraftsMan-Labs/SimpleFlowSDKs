# Telemetry Envelope V1

`telemetry-envelope.v1` is the canonical payload produced by SDK workflow-result bridges.

## Why it exists

- keeps Go/Python/Node telemetry outputs consistent
- gives control-plane analytics one stable shape to query
- enables user and conversation level tracking with strong trace correlation

## Core sections

- `identity`: `organization_id`, `agent_id`, `user_id`
- `trace`: `trace_id`, `conversation_id`, `request_id`, `run_id`, `sampled`
- `workflow`: `workflow_id`, terminal node, status, elapsed
- `usage`: prompt/completion/total/reasoning tokens, TTFT, throughput
- `model_usage[]`: per-model request and token usage
- `tool_usage[]`: tool call counts and errors
- `event_counts`: workflow event histogram

`nerdstats` and `raw` are optional and intended for deep diagnostics.

## Source of truth

See the full contract definition in `telemetry-envelope-v1-spec.md`.

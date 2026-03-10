# SUBAGENT TODO

## Mapping to TODO.md

- Parent task: `Align SimpleFlow telemetry with latest SimpleAgents nerdstats`
- Ownership: OpenCode primary agent
- Status: completed
- Policy decision locked: emit `null` for unavailable token metrics, not `0`.

## Completed workstreams

1. SDK extraction parity workstream (completed)
   - Node: add top-level nerdstats fallback (`workflow_result.nerdstats`).
   - Python: add direct metadata nerdstats extraction + top-level fallback.
   - Go: add top-level nerdstats fallback.

2. Usage semantics workstream (completed)
   - Switch unavailable token usage values to nullable across Node/Python/Go.
   - Propagate `token_metrics_available`, `token_metrics_source`, `llm_nodes_without_usage` into canonical usage payload.

3. Contract + docs workstream (completed)
   - Update `telemetry-envelope.v1` docs/spec for nullable usage and availability metadata.
   - Clarify compatibility expectations for control-plane analytics consumers.

4. Regression quality workstream (completed)
   - Add Node/Python/Go tests for extraction order and nullable usage behavior.
   - Add assertions for `total_reasoning_tokens` handling.
   - Run cross-language parity checks.

## Exit criteria (met)

- All SDKs extract nerdstats from the same source precedence.
- Canonical payload carries nullable usage when unavailable plus explicit availability/source metadata.
- Tests pass in Node/Python/Go with parity on control-plane-facing telemetry payloads.

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

## Mapping to TODO.md (current)

- Parent task: `Align SDK auth + strict chat schema with control-plane chat updates`
- Ownership: OpenCode primary agent
- Status: completed

## Current workstreams

1. Auth helpers workstream (completed)
   - Python: add auth session create/refresh/token validation methods.
   - Node: add auth session create/refresh/token validation methods.

2. Strict chat schema workstream (completed)
   - Add `output_data` support to chat writes.
   - Enforce role constraints and reject unknown top-level payload keys.

3. SimpleAgents ingestion workstream (completed)
   - Add Python/Node helper methods to map workflow result objects into strict assistant chat payloads.

4. Message output API workstream (completed)
   - Add Python/Node wrappers to read and upsert per-message output payloads.

5. TypeScript DX workstream (completed)
   - Add Node `index.d.ts` declarations and package `types` entry for typed usage of new helpers.

6. Verification workstream (completed)
   - Run Python + Node tests and resolve any failures.

## Mapping to TODO.md (latest)

- Parent task: `Add runnable Python reference script for SimpleAgents -> SDK chat ingestion`
- Ownership: OpenCode primary agent
- Status: completed

1. Example implementation workstream (completed)
   - Add runnable Python script to authenticate, write user + assistant messages, and verify message output.

2. Fixture and docs workstream (completed)
   - Add sample workflow result fixture and usage README for local execution.

3. Execution validation workstream (completed)
   - Execute script against localhost and capture auth response behavior.

## Mapping to TODO.md (latest)

- Parent task: `Add runnable Node/TS reference scripts for SimpleAgents -> SDK chat ingestion`
- Ownership: OpenCode primary agent
- Status: completed

1. Node example implementation workstream (completed)
   - Add runnable JavaScript script using SDK auth/session/chat helpers and SimpleAgents result ingestion.

2. TypeScript reference workstream (completed)
   - Add typed TypeScript variant mirroring JS flow and SDK method usage.

3. Validation workstream (completed)
   - Execute Node script against localhost with provided credentials and verify chat/session/output persistence.

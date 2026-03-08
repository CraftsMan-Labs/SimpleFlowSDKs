# TODO

## Parent Task: SimpleFlow SDK foundation (Go + Python)

- Status: completed
- Why: establish SDK boundaries and DX so SimpleAgents integrations can adopt a stable platform contract.
- Expected outcome: both SDKs provide equivalent control-plane/runtime APIs and telemetry bridge behavior.

### Subtasks

1. Status: completed
   - Add control-plane and runtime APIs (`register_runtime`, `invoke`, `write_event`, `write_chat_message`, `publish_queue_contract`).
2. Status: completed
   - Add workflow-result bridge API (`write_event_from_workflow_result`) that maps trace metadata fields.
3. Status: completed
   - Add telemetry bridge (`with_telemetry(...).emit_span(...)`) with `simpleflow` and `otlp` modes.
4. Status: completed
   - Add tests for runtime-event bridge behavior and telemetry sampling/emit behavior.
5. Status: completed
   - Copy `.opencode` guidance folder from SimpleFlow to keep shared agent workflows available here.
6. Status: completed
   - Update repository and language docs to reflect current SDK interfaces.

## Technical Notes

- `sample_rate` is validated as finite and in the inclusive range `0.0..1.0`.
- Sampling decision for telemetry spans is deterministic from `trace_id`.
- `write_event_from_workflow_result(...)` extracts `metadata.telemetry` and `metadata.trace.tenant` when available.

## Parent Task: SDK trust/lifecycle parity updates (Go + Python)

- Status: completed
- Why: align runtime trust configuration and lifecycle endpoint helpers across SDKs for consistent remote runtime integration behavior.
- Expected outcome: Go and Python SDKs both support shared-key/asymmetric verification expectations and lifecycle helper methods with test coverage.

### Subtasks

1. Status: completed
   - Add Go invoke token verifier shared-key HS256 mode while preserving existing JWKS/asymmetric verification.
2. Status: completed
   - Add Go + Python runtime registration lifecycle helpers for activate/deactivate/validate endpoints.
3. Status: completed
   - Clarify Python verifier usage for HS256 and RS256 and add coverage for shared-key flows.
4. Status: completed
   - Update SDK docs/READMEs for new trust and lifecycle APIs.
5. Status: completed
   - Run Go and Python test suites.

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

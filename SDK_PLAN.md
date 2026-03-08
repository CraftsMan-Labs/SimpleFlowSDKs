# SimpleFlow SDK Plan

## Objective

Keep SDK responsibilities clear:

- SimpleAgents handles workflow execution and trace context generation.
- SimpleFlow SDKs handle platform transport, auth, runtime writes, and telemetry routing.

## Phase 1 (Implemented)

- Expose core APIs in Go and Python:
  - `register_runtime(...)`
  - `invoke(...)`
  - `write_event(...)`
  - `write_chat_message(...)`
  - `publish_queue_contract(...)`
- Add workflow adapter API:
  - `write_event_from_workflow_result(...)`
- Add telemetry bridge:
  - `with_telemetry(mode="simpleflow"|"otlp", sample_rate=...)`
  - `emit_span(...)`
- Validate telemetry sampling config and use deterministic trace-id-based sampling.

## Phase 2 (Next)

- Finalize and freeze `POST /v1/runtime/events` envelope schema in docs.
- Add explicit compatibility matrix:
  - `SimpleAgents version x SDK version x SimpleFlow API contract`
- Expand tests for:
  - non-dict/typed workflow result normalization edge cases
  - invoke response decode failures
  - mode-specific telemetry behavior parity across languages

## Phase 3 (Release Readiness)

- Add semver changelog entries for both SDK packages.
- Add language-specific release automation and publishing checklist.
- Add integration examples against SimpleFlowTemplates.

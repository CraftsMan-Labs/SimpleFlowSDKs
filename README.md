# SimpleFlow SDKs

Language SDKs for integrating remote runtimes with the SimpleFlow control plane.

## Contents

- `go/simpleflow`: Go SDK client, auth token verifier, and contract types.
- `python/simpleflow_sdk`: Python SDK client, auth token verifier, and contract dataclasses.
- `.opencode`: shared agent skills and automation guidance copied from SimpleFlow.

## Scope

- Publish and version SDKs independently of control-plane releases.
- Keep runtime integration behavior consistent across languages.
- Follow control-plane contract versions and compatibility matrix.

## Current API Surface

- Control plane: `register_runtime(...)`, `invoke(...)`.
- Runtime lifecycle: `activate_runtime_registration(...)`, `deactivate_runtime_registration(...)`, `validate_runtime_registration(...)`.
- Runtime writes: `write_event(...)`, `write_chat_message(...)`, `publish_queue_contract(...)`.
- Chat history: `list_chat_history_messages(...)`, `create_chat_history_message(...)`, `update_chat_history_message(...)`.
- Workflow bridge: `write_event_from_workflow_result(...)`.
- Telemetry bridge: `with_telemetry(...).emit_span(...)` with `simpleflow` and `otlp` modes.

## Compatibility

- Version compatibility and contract mapping are tracked in `COMPATIBILITY_MATRIX.md`.

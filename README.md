# SimpleFlow SDKs

Language SDKs for integrating remote runtimes with the SimpleFlow control plane.

## Contents

- `go/simpleflow`: Go SDK client, auth token verifier, and contract types.
- `python/simpleflow_sdk`: Python SDK client, auth token verifier, and contract dataclasses.
- `node/simpleflow_sdk`: Node SDK client for runtime APIs, workflow bridge, and telemetry bridge.
- `.opencode`: shared agent skills and automation guidance copied from SimpleFlow.

## Scope

- Publish and version SDKs independently of control-plane releases.
- Keep runtime integration behavior consistent across languages.
- Follow control-plane contract versions and compatibility matrix.

## Current API Surface

- Control plane: `connect_runtime(...)`, `invoke(...)`.
- Runtime writes: `write_event(...)`, `write_chat_message(...)`, `publish_queue_contract(...)`.
- Chat history: `list_chat_history_messages(...)`, `create_chat_history_message(...)`, `update_chat_history_message(...)`.
- Workflow bridge: `write_event_from_workflow_result(...)`.
- Telemetry bridge: `with_telemetry(...).emit_span(...)` with `simpleflow` and `otlp` modes.
- Canonical workflow telemetry payload: `telemetry-envelope.v1` (see `docs/telemetry-envelope-v1-spec.md`).

## Compatibility

- Version compatibility and contract mapping are tracked in `docs/compatibility-matrix.md`.

## Documentation

- VitePress docs source lives in `docs/`.
- Production docs URL: `https://docs.simpleflow-sdk.craftsmanlabs.net`.
- Local docs commands: `make docs-dev`, `make docs-build`, `make docs-preview`.

## Developer commands

Use the root `Makefile` for common workflows:

- `make test` runs Go, Python, and Node tests.
- `make test-node` runs Node SDK tests.
- `make lint-go` and `make fmt-go` run Go quality checks.
- `make check-publish` runs release readiness checks.
- `make check-publish-all` runs release checks plus dry-run publish checks.
- `make publish-python-dry` builds Python artifacts without uploading.
- `make publish-python` uploads Python artifacts with Doppler + `uv publish`.
- `make publish-node-dry` runs npm publish dry-run for Node SDK.
- `make publish-node` uploads Node package using env token or local npm session.
- `make publish-node-doppler` uploads Node package with Doppler + `npm publish`.
- `make publish-all` publishes both Python and Node SDK packages.
- `make version-patch` / `make version-minor` / `make version-major` bump Python + Node versions together.
- `make version-patch AUTO_GIT=1` (or minor/major/set) auto-commits, tags, and pushes the release.
- `make release-patch` / `make release-minor` / `make release-major` bump version and auto commit/tag/push in one command.
- `make publish-go-tag VERSION=vX.Y.Z` creates and pushes a Go release tag.

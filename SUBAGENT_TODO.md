# SUBAGENT TODO

No subagents have been spawned yet for this refactor.

## Mapping to TODO.md

- Parent task: `Canonical telemetry platform refactor (SDKs + Control Plane)`
- Ownership: OpenCode primary agent
- Status: in_progress

## Planned workstreams

1. Contract workstream
   - Author `TelemetryEnvelopeV1` schema and fixture set.
   - Define required/optional fields and validation behavior.

2. SDK workstream
   - Go refactor to canonical envelope.
   - Python refactor to canonical envelope.
   - Node SDK implementation for parity.

3. Control-plane ingestion + analytics workstream
   - Canonical envelope parser/validator at ingest boundary.
   - Normalized analytics fact tables/materialized views.
   - Usage + cost aggregation endpoints.

4. Frontend analytics workstream
   - New model/user/conversation/tool and cost views.
   - Date-range and dimension filters.

5. Quality + reliability workstream
   - Cross-language parity tests.
   - End-to-end ingest-to-analytics assertions.
   - Runtime write load/performance tests.

## Exit criteria

- Canonical schema adopted in all SDKs and control plane.
- Analytics endpoint returns accurate daily/model/user/conversation/tool usage and cost metrics.
- Cross-language tests pass with deterministic parity guarantees.

## Progress update

- Added `docs/telemetry-envelope-v1-spec.md` as canonical payload spec.
- Refactored Go and Python workflow-result bridges to emit `telemetry-envelope.v1` payload.
- Added model usage, tool usage, usage summary, and event count normalization in both SDKs.
- Added/updated Go and Python tests to validate canonical payload emission.
- Updated control-plane analytics SQL to read canonical payload sections (`payload.usage.*`, `payload.workflow.*`).
- Added Node SDK parity implementation with workflow bridge, telemetry bridge, and test coverage.

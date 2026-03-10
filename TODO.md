# TODO

## Parent Task: Canonical telemetry platform refactor (SDKs + Control Plane)

- Status: in_progress
- Why: replace ad-hoc telemetry mapping with a single canonical contract and analytics-grade ingestion model while system is still in dev.
- Expected outcome: deterministic, language-parity telemetry with reliable usage/cost analytics by day, model, user, conversation, and tool.

### Subtasks

1. Status: completed
   - Define and freeze `TelemetryEnvelopeV1` JSON schema as the single telemetry contract across SDKs and control plane.
2. Status: completed
   - Add canonical workflow-result normalizer in SDKs producing `identity`, `trace`, `workflow`, `usage`, `model_usage`, `tool_usage`, `event_counts`, and optional `raw`.
3. Status: completed
   - Refactor Go SDK telemetry and workflow bridge APIs to emit only canonical envelope.
4. Status: completed
   - Refactor Python SDK telemetry and workflow bridge APIs to emit only canonical envelope.
5. Status: completed
   - Add Node SDK with parity APIs (`writeEvent`, `writeChatMessage`, `publishQueueContract`, workflow bridges, telemetry bridge).
6. Status: in_progress
   - Enforce strict correlation requirements (`organization_id`, `agent_id`, `user_id`, `conversation_id`, `request_id`, `run_id`, `trace_id`) and deterministic sampling parity across all SDKs.
7. Status: pending
   - Add idempotency defaults and retry-safe behavior in all runtime write helpers.
8. Status: in_progress
   - Refactor control-plane ingestion to parse canonical envelope into normalized analytics facts (not query-time raw JSON extraction).
9. Status: pending
   - Add analytics fact tables/materialized views for daily workflow/model/user/conversation/tool usage.
10. Status: pending
    - Add pricing model and cost computation pipeline (input/output/reasoning token rates with effective-date versioning).
11. Status: in_progress
   - Expand analytics API (`/v1/control-plane/analytics/overview`) with model/day/user/conversation/tool breakdowns and cost metrics.
12. Status: pending
    - Update frontend analytics page to expose new breakdowns, filters, and cost views.
13. Status: in_progress
   - Add cross-language contract tests, ingestion-to-analytics integration tests, and load tests for runtime write endpoints.
14. Status: in_progress
   - Update compatibility matrix and docs to reflect canonical telemetry contract and migration completion.

## Technical Notes

- No legacy compatibility layer: canonical contract is source of truth.
- Keep event-log + normalized-facts hybrid architecture for auditability and fast analytics.
- Sampling must be deterministic and equivalent across Go/Python/Node implementations.
- Control-plane analytics should read normalized facts by default; raw payload is debug-only.

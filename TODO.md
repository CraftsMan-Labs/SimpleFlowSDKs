# TODO

## Parent Task: Align SimpleFlow telemetry with latest SimpleAgents nerdstats

- Status: completed
- Why: SimpleAgents now emits richer nerdstats metadata and we need canonical, lossless control-plane ingestion.
- Decision: when token metrics are unavailable, send token usage values as `null` (not `0`) and include explicit availability/source signals.

### Subtasks

1. Status: completed
   - Expand nerdstats extraction source order in all SDKs (Node/Python/Go):
     - `workflow_result.nerdstats`
     - `workflow_result.metadata.nerdstats`
     - latest `workflow_completed.metadata.nerdstats`

2. Status: completed
   - Fix Python parity gap by checking direct `workflow_result.metadata.nerdstats` before event scanning.

3. Status: completed
   - Update usage normalization in Node/Python/Go so unavailable token metrics are `null` instead of `0`.

4. Status: completed
   - Extend canonical envelope usage section with nerdstats availability semantics:
     - `token_metrics_available`
     - `token_metrics_source`
     - `llm_nodes_without_usage`

5. Status: completed
   - Keep existing `payload.nerdstats` passthrough intact for deep diagnostics.

6. Status: completed
   - Update telemetry docs/spec to reflect nullable usage totals and availability/source fields.

7. Status: completed
   - Add Node regression tests for:
     - top-level nerdstats extraction
     - metadata nerdstats extraction
     - nullable usage totals when unavailable
     - `total_reasoning_tokens` mapping

8. Status: completed
   - Add Python regression tests for:
     - direct metadata nerdstats extraction parity
     - nullable usage totals when unavailable
     - `total_reasoning_tokens` mapping

9. Status: completed
   - Add Go regression tests for:
     - top-level nerdstats extraction
     - nullable usage totals when unavailable
     - `total_reasoning_tokens` mapping

10. Status: completed
    - Run cross-language test suite and verify parity for canonical telemetry envelope output.

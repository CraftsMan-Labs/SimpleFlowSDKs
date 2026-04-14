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

## Parent Task: Add per-language integration guides (auth + telemetry + chat + workflows)

- Status: completed
- Why: Provide a single page per SDK with end-to-end guidance for auth, telemetry, chat, and workflow execution.
- Decision: Keep each guide language-specific and aligned to current control-plane auth model (pass-through invoke bearer).

### Subtasks

1. Status: completed
   - Add Node guide with auth modes, telemetry bridge, chat usage, and SimpleAgents workflow example.

2. Status: completed
   - Add Python guide with auth modes, telemetry bridge, chat history usage, and SimpleAgents workflow example.

3. Status: completed
   - Add Go guide with auth modes, telemetry bridge, chat usage, and SimpleAgents workflow example.

4. Status: completed
   - Add guides to VitePress sidebar and cross-link from SDK overview pages.

## Parent Task: Align SDK auth + strict chat schema with control-plane chat updates

- Status: completed
- Why: Chat write schema is now strict (including assistant `output_data`) and user auth must rely on control-plane session tokens instead of local JWT issuance.
- Decision: add first-class auth session helpers (`create`, `refresh`, `validate`) and SimpleAgents-result chat helpers across Python/Node while keeping APIs minimal.

### Subtasks

1. Status: completed
   - Add Python auth session helpers for `POST /v1/auth/sessions`, `POST /v1/auth/sessions/refresh`, and `/v1/me` validation.

2. Status: completed
   - Add Node auth session helpers for `POST /v1/auth/sessions`, `POST /v1/auth/sessions/refresh`, and `/v1/me` validation.

3. Status: completed
   - Update chat write payload validation in Python/Node to allow `output_data`, enforce role constraints, and reject unknown top-level keys.

4. Status: completed
   - Add Python and Node helpers to derive assistant chat writes from SimpleAgents workflow `res` object.

5. Status: completed
   - Add Python and Node message-output endpoint wrappers (`get`/`upsert`) for `/v1/chat/messages/{message_id}/output`.

6. Status: completed
   - Add Node TypeScript declarations (`index.d.ts`) and package metadata for typed DX of new auth/chat helpers.

7. Status: completed
   - Update SDK docs and examples for login/refresh flow and `res`-based assistant message ingestion.

8. Status: completed
   - Run Python and Node SDK test suites and fix regressions.

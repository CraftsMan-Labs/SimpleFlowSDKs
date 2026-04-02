# Code Smell Remediation PR Execution Plan

Date: 2026-04-02  
Related:

- `code-review/code_smell_report.md`
- `code-review/code_smell_fix_plan.md`
- `code-review/code_smell_remediation_technical_plan.md`

## PR-1: Consolidate Transport Logic (Go + Python)

Objective: remove duplicated HTTP request/decode/error handling while preserving behavior.

### File-level TODOs

- `go/simpleflow/client.go`
  - Add internal `doJSON(method, path, body, out, extraHeaders)` helper.
  - Refactor duplicated transport blocks currently around `:276`, `:764`, `:817`, `:860` to use `doJSON`.
  - Keep public/internal call signatures unchanged.
- `python/simpleflow_sdk/client.py`
  - Add internal `_request_json(method, path, payload=None, extra_headers=None)` helper.
  - Refactor `_post` (`:863`), `_get` (`:900`), `_patch` (`:920`) to thin wrappers.
- `go/simpleflow/client_test.go`
  - Add/adjust tests for empty body, malformed JSON, and non-2xx mapping parity.
- `python/tests/test_client.py`
  - Add/adjust matching transport behavior tests.

### Validation

- Go tests pass.
- Python tests pass.
- No behavior changes in error messages/status mapping.

---

## PR-2: Fast Performance Wins (Low Risk)

Objective: address low-risk high-frequency allocations/copies.

### File-level TODOs

- `python/simpleflow_sdk/client.py`
  - Replace `asdict` deep-copy hot path near `:39` with shallow conversion for known types.
  - Hoist allowlist sets from per-call allocations (`:558`, `:583`) to module-level constants.
- `node/simpleflow_sdk/index.js`
  - Hoist repeated `new Set([...])` allowlists (`:371`, `:399`) to module-level constants.
- `go/simpleflow/client.go`
  - Reduce avoidable reboxing at `:610` where feasible.
  - Replace hot-loop `fmt.Sprintf` fallback patterns around `:470`, `:601`, `:629` with direct type-switch string conversions.

### Validation

- Existing unit tests pass in all three SDKs.
- Optional micro-bench/sanity timing shows no regressions.

---

## PR-3: Lifecycle and Workflow Complexity Refactor

Objective: reduce branch-heavy orchestration and large-function responsibilities.

### File-level TODOs

- `python/simpleflow_sdk/client.py`
  - Extract `resolve_workflow_context(...)` from `write_event_from_workflow_result` (`:704`).
  - Refactor `ensure_runtime_registration_active` (`:482`) into smaller state-step helpers.
- `go/simpleflow/client.go`
  - Extract workflow context resolution from `WriteEventFromWorkflowResult` (`:338`).
  - Simplify lifecycle state paths around `:136`, `:144`, `:152`.
  - Reduce constructor default branch clutter near `NewClient` (`:48`) via helper/table approach.
- `node/simpleflow_sdk/index.js`
  - Extract `resolveWorkflowContext(...)` around `writeEventFromWorkflowResult` (`:468`).
  - Refactor `ensureRuntimeRegistrationActive` (`:316`) into clear staged helper calls.

### Validation

- No API signature change.
- Snapshot outputs for workflow payloads remain identical.

---

## PR-4: Introduce Typed Domain Models (Additive)

Objective: add strict model contracts without breaking current consumers.

### File-level TODOs

- `python/simpleflow_sdk/` (new file if needed: `types.py`)
  - Add `TypedDict`/dataclass models:
    - `TelemetryEnvelopeV1`, `UsageSummary`, `ModelUsageRow`, `ToolUsageRow`
    - `RuntimeRegistration`, `RuntimeActivationResult`
    - `InvokeResult`, `ChatSession`, `ChatHistoryMessage`
- `python/simpleflow_sdk/client.py`
  - Add parse/validation helpers returning typed models.
- `node/simpleflow_sdk/index.js`
  - Add JSDoc typedef contracts matching the same model names.
- `go/simpleflow/` (new models file recommended, e.g. `models.go`)
  - Add strict structs for telemetry/usage/runtime/chat/invoke domain.

### Validation

- Type/static checks pass where configured.
- Runtime behavior unchanged.

---

## PR-5: Endpoint-by-Endpoint Return Type Migration

Objective: route core methods through typed parsing while preserving compatibility.

### File-level TODOs

- `python/simpleflow_sdk/client.py`
  - Migrate dynamic-return endpoints (`:412`, `:419`, `:422`, `:429`, `:471`, `:482`, `:546`, `:627`, `:651`, `:675`, `:680`) to typed parsing internally.
  - Keep old public shape behavior where needed via compatibility conversion.
- `python/simpleflow_sdk/auth.py`
  - Type claims return for `verify` (`:62`) into explicit claims model.
- `node/simpleflow_sdk/index.js`
  - Add endpoint-level validators/parsers for list/get/create/update response objects.
  - Narrow `_request` (`:654`) usage with typed call-site parsers.
- `go/simpleflow/client.go`
  - Replace map-heavy builders around `:392`, `:462`, `:489`, `:518`, `:579` with typed structs.
  - Minimize `any` helper reliance around `:511`, `:610`, `:641`, `:650`, `:655`, `:690`, `:914`.

### Validation

- New typed-path tests pass.
- Backward compatibility tests for existing return expectations pass.

---

## PR-6: Cross-SDK Contract Fixtures and Parity Tests

Objective: prevent drift across language implementations.

### File-level TODOs

- `contracts/telemetry-envelope-v1/` (new)
  - Add shared input/output fixture JSON cases.
- `contracts/runtime-registration/` (new)
  - Add registration action path templating parity fixtures.
- `go/simpleflow/client_test.go`
  - Add fixture-driven contract test adapter.
- `python/tests/test_client.py`
  - Add fixture-driven contract test adapter.
- `node/simpleflow_sdk/tests/client.test.js`
  - Add fixture-driven contract test adapter.

### Validation

- All SDKs pass same fixture set exactly.

---

## PR-7: Test Deduplication and Test Ergonomics

Objective: reduce repeated fixture/scaffolding code.

### File-level TODOs

- `python/tests/test_client.py`
  - Extract repeated setup patterns near `:130`, `:154`, `:183` into reusable factory/helpers.
- `python/tests/` (new helper module if needed)
  - Add `make_client_with_fake_http(...)` and shared assertions.
- `go/simpleflow/client_test.go`
  - Replace duplicated workflow/usage fixtures (`:28`, `:147`) with shared fixture loader.
- `node/simpleflow_sdk/tests/client.test.js`
  - Replace duplicated workflow/usage fixtures (`:40`, `:125`) with shared fixture loader.

### Validation

- Test runtime and readability improved.
- No assertion coverage loss.

---

## PR-8: Documentation Consolidation

Objective: keep feature-rich docs with less duplication/drift.

### File-level TODOs

- `docs/sdk-node-integration.md`
- `docs/sdk-python-integration.md`
- `docs/sdk-go-integration.md`
  - Extract common runtime/auth/integration flow narrative into shared section pattern.
- `docs/sdk-node.md`, `docs/sdk-python.md`, `docs/sdk-go.md`
  - Consolidate duplicated env-var/feature descriptions.
- `README.md`, `node/README.md`, `python/README.md`, `go/simpleflow/README.md`
  - Keep one canonical source for shared capability matrix; link instead of repeating large blocks.

### Validation

- Docs still cover all current features.
- No conflicting instructions across SDK docs.

---

## PR-9: Repo Hygiene and Artifact Guardrails

Objective: keep repo concise and prevent accidental bloat.

### File-level TODOs

- `.github/workflows/docs.yml` (or additional workflow file)
  - Add guard step to fail if generated artifacts/binaries are tracked (`node_modules`, `dist`, caches, egg-info, etc.).
- `Makefile` or `scripts/clean.*` (new)
  - Add cleanup command to remove generated artifacts:
    - `docs/node_modules`
    - `examples/simpleflow-hr-agent/node_modules`
    - `.opencode/node_modules`
    - `docs/.vitepress/dist`
    - `python/dist`
- `.gitignore`
  - Ensure all generated/cache paths are ignored.
- `CNAME` / `docs/CNAME`
  - Keep single canonical file location (whichever deployment flow requires).

### Validation

- CI blocks accidental artifact commits.
- Cleanup command works locally and is documented.

---

## Cross-PR Safety Checklist (Apply to Every PR)

- Add or update regression tests before changing behavior-heavy internals.
- Keep public API signatures stable unless planned version bump.
- Ensure changelog/docs updated for any new typed methods or deprecations.
- Run language test suites impacted by the PR.
- Confirm examples continue to work.

## Recommended Owner Split

- Go owner: PR-1, PR-3, PR-5, PR-6 (Go adapter)
- Python owner: PR-1, PR-2, PR-3, PR-4, PR-5, PR-6 (Python adapter), PR-7
- Node owner: PR-2, PR-3, PR-4, PR-5, PR-6 (Node adapter)
- Docs/DevEx owner: PR-8, PR-9

## Release Plan

1. Merge PR-1 through PR-3 first (internal refactors, no breaking changes).
2. Merge PR-4 and PR-5 with deprecation notices and migration notes.
3. Merge PR-6 as enforcement gate for parity.
4. Merge PR-7 to PR-9 for quality and repo hygiene completion.

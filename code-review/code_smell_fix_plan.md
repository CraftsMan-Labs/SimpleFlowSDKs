# Code Smell Violation Fix Plan

Date: 2026-04-02  
Source report: `code-review/code_smell_report.md`

## Goal

Eliminate the reported DRY, KISS/pragmatism, ambiguity, complexity, and optimization violations while preserving behavior and feature coverage across Go, Python, and Node SDKs.

## Delivery Strategy

- Use incremental PRs with behavior-preserving refactors first, then typing/model hardening.
- Keep all public API behavior backward compatible unless explicitly versioned.
- Add parity tests before broad refactors in shared logic areas.

## Workstreams

## WS1: Transport DRY Consolidation (High Priority)

### Scope

- Go duplicate request flow in `go/simpleflow/client.go:276`, `go/simpleflow/client.go:764`, `go/simpleflow/client.go:817`, `go/simpleflow/client.go:860`
- Python duplicate request flow in `python/simpleflow_sdk/client.py:863`, `python/simpleflow_sdk/client.py:900`, `python/simpleflow_sdk/client.py:920`

### Implementation

1. Introduce Go internal helper `doJSON(method, path, requestBody, out, extraHeaders)` and migrate current `get/post/patch` helpers to wrappers.
2. Introduce Python internal helper `_request_json(method, path, payload=None, headers=None)` and migrate `_get/_post/_patch` to wrappers.
3. Preserve existing error classes/messages and status handling semantics.

### Done Criteria

- No duplicate HTTP decode/status blocks remain in the targeted methods.
- Existing tests pass unchanged.

---

## WS2: Complexity and KISS Refactors (High Priority)

### Scope

- Python broad-responsibility class at `python/simpleflow_sdk/client.py:356`
- Go branch-heavy defaults in `go/simpleflow/client.go:48`
- Workflow-context and lifecycle complexity at:
  - `python/simpleflow_sdk/client.py:704`, `python/simpleflow_sdk/client.py:482`
  - `go/simpleflow/client.go:338`, `go/simpleflow/client.go:136`, `go/simpleflow/client.go:144`, `go/simpleflow/client.go:152`
  - `node/simpleflow_sdk/index.js:468`, `node/simpleflow_sdk/index.js:316`

### Implementation

1. Extract pure helpers:
   - `resolveWorkflowContext(...)`
   - `ensureRegistered/ensureValidated/ensureActivated`
2. Reduce branch nesting using table-driven/default helper patterns.
3. Split Python internals into focused components while keeping `SimpleFlowClient` as facade.

### Done Criteria

- Reduced branch depth in targeted methods.
- Large function responsibilities split into focused units.

---

## WS3: Strict Return Type Migration (High Priority)

### Scope

- Python dynamic return hotspots listed in `code-review/code_smell_report.md` section 3.
- Node dynamic object return hotspots in `node/simpleflow_sdk/index.js` (`extractNerdstats`, `usageSummary`, `modelUsage`, `toolUsage`, `buildCanonicalTelemetryEnvelope`, `_request`, runtime/chat list methods).
- Go dynamic map-heavy hotspots in `go/simpleflow/client.go` (`buildCanonicalTelemetryEnvelope`, `extractNerdstats`, `buildUsage`, `buildModelUsage`, `buildToolUsage`, `normalizeMap`, casting helpers).

### Implementation

1. Define shared domain model names across SDKs:
   - `TelemetryEnvelopeV1`
   - `UsageSummary`
   - `ModelUsageRow`
   - `ToolUsageRow`
   - `RuntimeRegistration`, `RuntimeActivationResult`
   - `InvokeResult`, `ChatSession`, `ChatHistoryMessage`
2. Python:
   - Add `TypedDict`/dataclass return types.
   - Introduce typed decode path in transport and endpoint-specific parsers.
3. Node:
   - Add JSDoc typedefs immediately; optionally stage migration to TypeScript in later phase.
   - Implement generic request typing pattern in docs/tests and endpoint validators.
4. Go:
   - Replace dynamic maps with concrete structs in envelope/usage builders.
   - Reduce reliance on generic `any` casting helpers.

### Done Criteria

- Core production methods stop returning unbounded generic maps/objects where strict models exist.
- Public docs updated to reflect strict response contracts.

---

## WS4: Performance Fixes (High Priority)

### Scope

- Python deep-copy normalization at `python/simpleflow_sdk/client.py:39`
- Go JSON round-trip normalization at `go/simpleflow/client.go:903`, `go/simpleflow/client.go:908`
- Sequential lifecycle call latency in Python/Node (`python/simpleflow_sdk/client.py:496`, `python/simpleflow_sdk/client.py:532`, `python/simpleflow_sdk/client.py:535`, `node/simpleflow_sdk/index.js:323`, `node/simpleflow_sdk/index.js:350`, `node/simpleflow_sdk/index.js:351`)
- Repeated allowlist allocations in Python/Node
- Go copy/reboxing and fallback formatting overhead in `go/simpleflow/client.go:610`, `go/simpleflow/client.go:470`, `go/simpleflow/client.go:601`, `go/simpleflow/client.go:629`

### Implementation

1. Replace Python `asdict` hot-path usage with shallow/typed extraction.
2. Add Go typed fast paths before marshal/unmarshal fallback.
3. Cache active runtime registration with TTL in Python/Node clients.
4. Hoist allowlist sets/constants to module scope.
5. Remove avoidable slice reboxing; use typed loops and primitive type-switches.

### Done Criteria

- Measurable latency/allocation reduction in targeted hot paths.
- No behavior regression in telemetry/event outputs.

---

## WS5: Cross-SDK Contract Parity (Medium Priority)

### Scope

- Telemetry envelope duplication and drift risk across:
  - `go/simpleflow/client.go:392`
  - `python/simpleflow_sdk/client.py:271`
  - `node/simpleflow_sdk/index.js:182`

### Implementation

1. Add shared fixture set under a common path (for example `contracts/telemetry-envelope-v1/*.json`).
2. Add per-language conformance tests to assert exact shape/parity.
3. Add one contract test for registration action path templating parity.

### Done Criteria

- Envelope and registration path outputs match shared fixtures across SDKs.

---

## WS6: Test and Docs Deduplication (Medium Priority)

### Scope

- Duplicate tests in:
  - `go/simpleflow/client_test.go:28`, `go/simpleflow/client_test.go:147`
  - `node/simpleflow_sdk/tests/client.test.js:40`, `node/simpleflow_sdk/tests/client.test.js:125`
  - `python/tests/test_client.py:263`, `python/tests/test_client.py:343`
- Duplicate integration docs and SDK references in:
  - `docs/sdk-node-integration.md`, `docs/sdk-python-integration.md`, `docs/sdk-go-integration.md`
  - `docs/sdk-node.md`, `docs/sdk-python.md`, `docs/sdk-go.md`
  - `README.md`, `node/README.md`, `python/README.md`, `go/simpleflow/README.md`

### Implementation

1. Move shared test payloads to centralized fixtures; keep only language-specific assertions in each suite.
2. Add Python test factory helpers for client/mock setup.
3. Consolidate repeated docs into shared sections with language-specific snippets.

### Done Criteria

- Reduced duplicate test scaffolding and fixture drift.
- Single source of truth for shared integration guidance.

---

## WS7: Repo Footprint and Hygiene (Medium Priority)

### Scope

- Generated/local artifact cleanup opportunities:
  - `docs/node_modules`
  - `examples/simpleflow-hr-agent/node_modules`
  - `.opencode/node_modules`
  - `docs/.vitepress/dist`
  - `python/dist`
- Duplicate DNS config check:
  - `CNAME`, `docs/CNAME`

### Implementation

1. Add root cleanup target (e.g., `make clean` or script) for generated artifacts.
2. Add CI guardrails to reject tracked artifacts (`node_modules`, `dist`, cache/build outputs).
3. Keep one canonical `CNAME` location.

### Done Criteria

- Clean workspace routine documented and enforced.
- Artifact/binary accidental commits blocked in CI.

---

## Recommended PR Sequence

1. PR-1: WS1 transport helper consolidation (Go + Python)
2. PR-2: WS4 quick perf wins (allowlist constants, Python `asdict` hot path)
3. PR-3: WS2 workflow/lifecycle helper extraction
4. PR-4: WS3 model/type introduction (non-breaking, additive)
5. PR-5: WS3 endpoint-by-endpoint strict return migration
6. PR-6: WS5 contract fixtures + parity tests
7. PR-7: WS6 test fixture consolidation
8. PR-8: WS6 docs deduplication
9. PR-9: WS7 cleanup tooling + CI artifact guardrails

## Validation and Acceptance Gates

- Unit/integration tests pass for all SDKs after each PR.
- No API behavior regressions in existing examples.
- Conformance fixtures pass in Go/Python/Node.
- Static checks/type checks show reduced dynamic return usage.
- Performance sanity checks show no regressions in write-event and lifecycle hot paths.

## Risks and Mitigations

- Risk: typing migration breaks consumers expecting loose objects.
  - Mitigation: additive typing first, deprecation window, changelog notes.
- Risk: helper consolidation changes subtle error semantics.
  - Mitigation: snapshot tests for status/error payloads before refactor.
- Risk: cross-language parity refactors drift over time.
  - Mitigation: mandatory shared fixture tests in CI.

## Definition of Complete

- All high-severity items in `code-review/code_smell_report.md` resolved.
- Medium-severity items either resolved or documented with explicit rationale/defer date.
- No unresolved ambiguous return type in core SDK public APIs without an approved exception.
- Repo hygiene checks active and passing.

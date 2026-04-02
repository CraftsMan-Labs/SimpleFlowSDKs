# Code Smell Remediation Technical Plan

Date: 2026-04-02  
Inputs:

- `code-review/code_smell_report.md`
- `code-review/code_smell_fix_plan.md`

## Objectives

1. Remove high/medium severity code smells without breaking public behavior.
2. Reduce duplication and cyclomatic complexity in transport, lifecycle, and telemetry flows.
3. Replace ambiguous return shapes with strict contracts in a backward-safe rollout.
4. Improve performance in known hotspots.

## Non-Breaking Migration Principles

- Keep existing public methods and signatures stable in phase 1.
- Introduce internal helpers first, then migrate callers incrementally.
- Add snapshot/parity tests before behavior refactors.
- Ship typed return models as additive wrappers before enforcing strict outputs.
- Guard risky changes behind compatibility paths and feature flags where needed.

## Architecture Targets

### A) Transport Layer Consolidation

Current issue:

- Duplicate request/response handling across Go and Python methods.

Target:

- One transport core per SDK with uniform behavior for:
  - URL/path normalization
  - auth header injection
  - idempotency headers
  - status/error mapping
  - response decode and empty-body handling

### B) Domain Model Layer (Strict Contracts)

Current issue:

- `dict`/`map`/generic object returns in core production APIs.

Target:

- Strong typed models for telemetry, usage, runtime registration, invoke responses, chat resources.

### C) Orchestration vs Resolution Split

Current issue:

- Large methods combine extraction, fallback resolution, transformation, transport, and error handling.

Target:

- Small orchestration methods calling pure helper functions:
  - `resolveWorkflowContext`
  - `buildUsageSummary`
  - `buildEnvelope`
  - lifecycle state helpers

### D) Cross-SDK Contract Parity

Current issue:

- Similar behavior implemented independently and can drift.

Target:

- Shared fixture-based contract tests for envelope and lifecycle path templating.

---

## Execution Plan by Phase

## Phase 0: Safety Net (Required Before Refactor)

### Tasks

1. Add golden fixtures for:
   - telemetry envelope input/output
   - workflow result -> event payload
   - lifecycle activation sequences
2. Add snapshot tests for error/status mapping per SDK transport.
3. Add regression tests for empty body, malformed JSON, and non-2xx responses.

### Pseudocode

```text
for each sdk in [go, python, node]:
  load fixture cases
  run current implementation
  store normalized outputs as baseline snapshots
  assert stable for future refactors
```

Exit criteria:

- Baseline tests pass in CI for all SDKs.

---

## Phase 1: DRY Transport Refactor (No API surface change)

### Python technical plan

1. Add `_request_json(method, path, payload=None, extra_headers=None)`.
2. Move shared logic from `_get/_post/_patch` into this helper.
3. Keep `_get/_post/_patch` as thin wrappers to preserve call sites.

Pseudocode:

```python
def _request_json(method, path, payload=None, extra_headers=None):
    url = join(base_url, normalize(path))
    headers = build_headers(extra_headers)
    response = http.request(method, url, json=payload, headers=headers)

    if response.status_code >= 400:
        raise map_http_error(response)

    if not response.content:
        return {}

    try:
        return response.json()
    except JSONDecodeError:
        raise ProtocolError("invalid JSON response")

def _get(path):
    return _request_json("GET", path)

def _post(path, payload=None, headers=None):
    return _request_json("POST", path, payload, headers)
```

### Go technical plan

1. Add `doJSON(method, path string, body any, out any, extraHeaders map[string]string) error`.
2. Rewire existing `postJSON...`, `patchJSON...`, `getJSON` to call `doJSON`.

Pseudocode:

```go
func (c *Client) doJSON(method, path string, body any, out any, extraHeaders map[string]string) error {
    req, err := c.newRequest(method, normalizePath(path), body)
    if err != nil { return err }

    applyHeaders(req, extraHeaders)
    resp, err := c.httpClient.Do(req)
    if err != nil { return err }
    defer resp.Body.Close()

    if resp.StatusCode >= 400 { return mapHTTPError(resp) }
    if out == nil { return nil }

    if isEmptyBody(resp.Body) { return nil }
    return decodeJSON(resp.Body, out)
}
```

Exit criteria:

- No behavior change in existing transport tests.
- Duplicate transport blocks removed.

---

## Phase 2: Complexity/KISS Reduction

### Lifecycle flow split

Problem:

- `ensureRuntimeRegistrationActive` style methods are branch-heavy and sequential.

Technical plan:

1. Extract deterministic state machine helpers:
   - `findActiveRegistration`
   - `validateRegistration`
   - `activateRegistration`
2. Keep top-level method as orchestrator.

Pseudocode:

```text
ensure_active(identity):
  reg = find_active_registration(identity)
  if reg exists:
    return ActiveResult(registration=reg, validation=None)

  candidate = register_if_missing(identity)
  validation = validate(candidate.id)
  activated = activate(candidate.id)
  return ActiveResult(registration=activated, validation=validation)
```

### Workflow context extraction split

Problem:

- Multi-source fallback chains inside one method.

Technical plan:

1. Add pure `resolveWorkflowContext(result, overrides)`.
2. Add pure `buildCanonicalEnvelope(context, nerdstats, usage)`.
3. Keep writer methods focused on transport call only.

Pseudocode:

```text
resolve_workflow_context(result, overrides):
  tenant_id = first_non_empty(
    overrides.tenant_id,
    result.trace.tenant_id,
    result.tenant_id
  )
  trace_id = first_non_empty(overrides.trace_id, result.trace.id, result.trace_id)
  session_id = first_non_empty(overrides.session_id, result.session_id)
  return Context(tenant_id, trace_id, session_id)
```

Exit criteria:

- Target large methods reduced in responsibilities and branch depth.

---

## Phase 3: Strict Return Contract Rollout

### Rollout strategy (non-breaking)

1. Introduce internal typed models first.
2. Parse transport responses into typed models in new internal code paths.
3. Keep existing public methods returning old shapes temporarily.
4. Add new typed variants or typed wrappers.
5. Deprecate ambiguous returns and remove in major version.

### Canonical model set

- `TelemetryEnvelopeV1`
- `UsageSummary`
- `ModelUsageRow`
- `ToolUsageRow`
- `RuntimeRegistration`
- `RuntimeActivationResult`
- `InvokeResult`
- `ChatSession`
- `ChatHistoryMessage`

### Pseudocode (Python example)

```python
class RuntimeRegistration(TypedDict):
    id: str
    runtime_name: str
    status: Literal["pending", "active", "disabled"]

def register_runtime_typed(...) -> RuntimeRegistration:
    raw = self._request_json("POST", "/runtime/registrations", payload)
    return parse_runtime_registration(raw)

# backward-compatible method
def register_runtime(...):
    typed = self.register_runtime_typed(...)
    return dict(typed)
```

### Pseudocode (Go example)

```go
type UsageSummary struct {
    InputTokens  *int64   `json:"input_tokens,omitempty"`
    OutputTokens *int64   `json:"output_tokens,omitempty"`
    ElapsedMS    *float64 `json:"elapsed_ms,omitempty"`
}

func buildUsageTyped(...) UsageSummary {
    // typed extraction and conversion, no map[string]any
}
```

Exit criteria:

- Core APIs have typed internal models and typed parsing paths.
- Compatibility maintained for existing consumers.

---

## Phase 4: Performance Remediation

### Concrete fixes

1. Replace Python `asdict` in hot normalization path with shallow conversion.
2. Add Go fast path normalization for known types before JSON round-trip.
3. Hoist allowlist sets/constants in Python/Node to module scope.
4. Remove avoidable Go slice reboxing and `fmt.Sprintf` fallback in hot loops.
5. Add lifecycle active-registration cache (TTL + invalidation on auth/runtime change).

### Pseudocode (cache)

```text
if cache.has(identity_key) and not cache.expired(identity_key):
  return cache.get(identity_key)

result = ensure_active_remote(identity_key)
cache.put(identity_key, result, ttl=5m)
return result
```

### Pseudocode (Go normalization)

```go
func normalizeMap(v any) (map[string]any, error) {
    switch t := v.(type) {
    case map[string]any:
        return t, nil
    case KnownStructA:
        return mapFromKnownStructA(t), nil
    case KnownStructB:
        return mapFromKnownStructB(t), nil
    default:
        return normalizeByJSONRoundTrip(v) // fallback only
    }
}
```

Exit criteria:

- Hot path benchmark/allocation improvements are measurable.

---

## Phase 5: Cross-SDK Contract and Docs/Test Dedupe

### Technical plan

1. Add shared contract fixture directory for envelope/registration path cases.
2. Build adapter tests per SDK to run same fixture set.
3. Consolidate duplicated docs into shared narrative + language snippets.
4. Centralize repeated test fixtures and helper setup.

Pseudocode:

```text
for case in contract_fixtures:
  actual_go = go_adapter(case.input)
  actual_py = py_adapter(case.input)
  actual_node = node_adapter(case.input)
  assert normalize(actual_go) == case.expected
  assert normalize(actual_py) == case.expected
  assert normalize(actual_node) == case.expected
```

Exit criteria:

- One fixture source validates all SDK outputs.
- Reduced duplicated docs/test setup.

---

## Change Management and Release Safety

## Branching/PR policy

- One workstream per PR to isolate risk.
- Require green CI + contract fixtures + regression tests before merge.

## Backward compatibility policy

- Keep legacy methods active until typed replacements are stable.
- Emit deprecation notes in release docs.
- Remove deprecated ambiguous paths only in major bump.

## Verification matrix per PR

1. Unit tests (language-specific)
2. Contract fixture tests (cross-language)
3. Performance sanity checks on hot paths
4. Example scripts smoke tests
5. Docs consistency checks

---

## Deliverables Checklist

- [ ] Transport helper consolidation complete (Go, Python)
- [ ] Lifecycle/workflow context extraction complete (Go, Python, Node)
- [ ] Typed model layer introduced for core contracts
- [ ] Ambiguous return paths deprecated or replaced
- [ ] Performance hotspots remediated with benchmark evidence
- [ ] Shared parity fixtures and tests added
- [ ] Docs/tests deduplicated
- [ ] Repo artifact hygiene automation enabled

## Final Success Metrics

- Duplicate transport code eliminated in targeted files.
- Cyclomatic complexity reduced in flagged hotspots.
- Ambiguous return types removed from core paths or formally deprecated.
- Lower latency/allocation in event/lifecycle hot paths.
- No functional regression in API behavior and examples.

# SimpleFlow Python SDK (Remote Runtime)

This SDK helps Python remote runtime backends integrate with the SimpleFlow control plane.

## Features

- API client for auth/session helpers, runtime registration lifecycle orchestration (`list/activate/deactivate/validate/ensure_active`), invoke, runtime events, chat message writes, queue contract publication, and chat history list/create/update.
- Invoke token verification helper for control-plane issued tokens (HS256 shared key and RS256 public key/JWKS usage).
- Method-level auth token overrides on control-plane and lifecycle methods.
- Typed request errors (`SimpleFlowAuthenticationError`, `SimpleFlowAuthorizationError`, `SimpleFlowLifecycleError`).
- Typed dataclasses for common runtime payloads and telemetry span envelopes.
- Telemetry bridge with `simpleflow` and `otlp` modes.

## Install

```bash
pip install -e ./python
```

## Minimal usage

```python
from simpleflow_sdk import RuntimeEvent, SimpleFlowClient

client = SimpleFlowClient(base_url="https://api.simpleflow.example", api_token="runtime-token")
client.write_event(
    RuntimeEvent(
        type="runtime.invoke.accepted",
        agent_id="agent-1",
        run_id="run_123"
    )
)

telemetry = client.with_telemetry(mode="simpleflow", sample_rate=0.2)
telemetry.emit_span(
    span={"name": "llm.call", "start_time_ms": 1000, "end_time_ms": 1250},
    trace_id="trace_123",
    run_id="run_123",
    agent_id="agent-1",
)
```

## Security note: runtime endpoint allowlist

If your control-plane backend enables `RUNTIME_ENDPOINT_ALLOWLIST`, runtime registration calls from this SDK (`register_runtime` / `ensure_runtime_registration_active`) will fail with `400` unless the registration `endpoint_url` host is included in that allowlist.

## Auth verifier usage

```python
from simpleflow_sdk import InvokeTokenVerifier

hs_verifier = InvokeTokenVerifier.for_hs256_shared_key(
    issuer="https://api.simpleflow.example",
    audience="runtime",
    shared_key="local-dev-secret",
)

rs_verifier = InvokeTokenVerifier.for_rs256_public_key(
    issuer="https://api.simpleflow.example",
    audience="runtime",
    public_key=public_key_pem,
)

# You can also pass a key per call when needed.
claims = hs_verifier.verify(token)
```

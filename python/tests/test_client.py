from __future__ import annotations

import unittest
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types


class _NoopHTTPXClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def post(self, url: str, json: dict, headers: dict) -> object:
        raise RuntimeError("httpx stub client should be replaced in tests")

    def close(self) -> None:
        return None


httpx_stub = types.ModuleType("httpx")
setattr(httpx_stub, "Client", _NoopHTTPXClient)
sys.modules.setdefault("httpx", httpx_stub)

CLIENT_MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "simpleflow_sdk" / "client.py"
)
CLIENT_SPEC = spec_from_file_location("simpleflow_sdk_client", CLIENT_MODULE_PATH)
if CLIENT_SPEC is None or CLIENT_SPEC.loader is None:
    raise RuntimeError("failed to load simpleflow sdk client module for tests")
CLIENT_MODULE = module_from_spec(CLIENT_SPEC)
CLIENT_SPEC.loader.exec_module(CLIENT_MODULE)
SimpleFlowClient = CLIENT_MODULE.SimpleFlowClient
_should_sample = CLIENT_MODULE._should_sample


class _FakeResponse:
    def __init__(self, status_code: int = 204, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = "" if payload is None else "{}"

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no body")
        return self._payload


class _FakeHTTPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
        self.calls.append((url, json))
        return _FakeResponse()

    def close(self) -> None:
        return None


@dataclass(slots=True)
class _FakeSpan:
    name: str
    start_time_ms: int
    end_time_ms: int


class SimpleFlowClientTests(unittest.TestCase):
    def test_write_event_from_workflow_result_extracts_trace_fields(self) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]

        client.write_event_from_workflow_result(
            agent_id="agent_support_v1",
            workflow_result={
                "run_id": "run_123",
                "metadata": {
                    "telemetry": {"trace_id": "trace_123", "sampled": True},
                    "trace": {
                        "tenant": {
                            "conversation_id": "chat_123",
                            "request_id": "req_123",
                        }
                    },
                },
            },
        )

        _, payload = fake_http.calls[-1]
        self.assertEqual(payload["trace_id"], "trace_123")
        self.assertEqual(payload["conversation_id"], "chat_123")
        self.assertEqual(payload["request_id"], "req_123")

    def test_with_telemetry_simpleflow_emits_runtime_event(self) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]

        telemetry = client.with_telemetry(mode="simpleflow", sample_rate=1.0)
        telemetry.emit_span(
            span=_FakeSpan(name="llm.call", start_time_ms=10, end_time_ms=15),
            agent_id="agent_1",
            run_id="run_1",
            trace_id="trace_1",
        )

        _, payload = fake_http.calls[-1]
        self.assertEqual(payload["type"], "runtime.telemetry.span")
        self.assertEqual(payload["trace_id"], "trace_1")


class SamplingTests(unittest.TestCase):
    def test_should_sample_is_deterministic(self) -> None:
        first = _should_sample("trace_abc", 0.2)
        second = _should_sample("trace_abc", 0.2)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

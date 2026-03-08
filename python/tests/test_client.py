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

    def get(self, url: str, headers: dict) -> object:
        raise RuntimeError("httpx stub client should be replaced in tests")

    def patch(self, url: str, json: dict, headers: dict) -> object:
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
        self.calls_get: list[str] = []
        self.calls_patch: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
        self.calls.append((url, json))
        if url.endswith("/v1/runtime/registrations/reg_123/validate"):
            return _FakeResponse(
                payload={"validation_ok": True, "registration": {"id": "reg_123"}}
            )
        return _FakeResponse()

    def get(self, url: str, headers: dict) -> _FakeResponse:
        self.calls_get.append(url)
        return _FakeResponse(payload={"messages": [{"message_id": "m1"}]})

    def patch(self, url: str, json: dict, headers: dict) -> _FakeResponse:
        self.calls_patch.append((url, json))
        return _FakeResponse(payload={"message_id": "m1"})

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
        self.assertEqual(payload["event_type"], "runtime.workflow.completed")
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
        self.assertEqual(payload["event_type"], "runtime.telemetry.span")
        self.assertEqual(payload["trace_id"], "trace_1")

    def test_chat_history_list_method(self) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]

        messages = client.list_chat_history_messages(
            agent_id="agent_1", chat_id="chat_1", user_id="user_1", limit=10
        )
        self.assertEqual(messages[0]["message_id"], "m1")

    def test_runtime_registration_lifecycle_helpers(self) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]

        client.activate_runtime_registration("reg_123")
        client.deactivate_runtime_registration("reg_123")
        validation = client.validate_runtime_registration("reg_123")

        called_urls = [url for (url, _) in fake_http.calls]
        self.assertEqual(
            called_urls,
            [
                "https://api.example/v1/runtime/registrations/reg_123/activate",
                "https://api.example/v1/runtime/registrations/reg_123/deactivate",
                "https://api.example/v1/runtime/registrations/reg_123/validate",
            ],
        )
        self.assertEqual(validation["validation_ok"], True)


class SamplingTests(unittest.TestCase):
    def test_should_sample_is_deterministic(self) -> None:
        first = _should_sample("trace_abc", 0.2)
        second = _should_sample("trace_abc", 0.2)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

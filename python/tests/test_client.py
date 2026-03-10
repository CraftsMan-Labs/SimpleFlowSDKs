from __future__ import annotations

import unittest
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any
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

    def delete(self, url: str, headers: dict) -> object:
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
SimpleFlowAuthenticationError = CLIENT_MODULE.SimpleFlowAuthenticationError
SimpleFlowAuthorizationError = CLIENT_MODULE.SimpleFlowAuthorizationError
SimpleFlowLifecycleError = CLIENT_MODULE.SimpleFlowLifecycleError


class _FakeResponse:
    def __init__(
        self,
        status_code: int = 204,
        payload: dict | None = None,
        text: str | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        if text is not None:
            self.text = text
        else:
            self.text = "" if payload is None else "{}"

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no body")
        return self._payload


class _FakeHTTPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, dict]] = []
        self.calls_get: list[tuple[str, dict]] = []
        self.calls_patch: list[tuple[str, dict, dict]] = []
        self.calls_delete: list[tuple[str, dict]] = []
        self.error_by_post_url: dict[str, int] = {}
        self.error_by_get_url: dict[str, int] = {}
        self.registrations_payload: list[dict[str, Any]] = [{"id": "reg_1"}]

    def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
        self.calls.append((url, json, headers))
        status_code = self.error_by_post_url.get(url)
        if status_code is not None:
            return _FakeResponse(status_code=status_code, text="denied")
        if url.endswith("/v1/runtime/registrations/reg_123/validate"):
            return _FakeResponse(
                payload={"validation_ok": True, "registration": {"id": "reg_123"}}
            )
        if url.endswith("/v1/runtime/registrations"):
            return _FakeResponse(payload={"id": "reg_created"})
        if url.endswith("/v1/auth/sessions"):
            return _FakeResponse(payload={"session": {"id": "sess_1"}})
        return _FakeResponse()

    def get(self, url: str, headers: dict) -> _FakeResponse:
        self.calls_get.append((url, headers))
        status_code = self.error_by_get_url.get(url)
        if status_code is not None:
            return _FakeResponse(status_code=status_code, text="not allowed")
        if url.endswith("/v1/me"):
            return _FakeResponse(payload={"user_id": "user_1"})
        if "/v1/runtime/registrations?" in url:
            return _FakeResponse(payload={"registrations": self.registrations_payload})
        if "/v1/chat/history/sessions?" in url:
            return _FakeResponse(payload={"sessions": [{"chat_id": "chat_1"}]})
        return _FakeResponse(payload={"messages": [{"message_id": "m1"}]})

    def patch(self, url: str, json: dict, headers: dict) -> _FakeResponse:
        self.calls_patch.append((url, json, headers))
        return _FakeResponse(payload={"message_id": "m1"})

    def delete(self, url: str, headers: dict) -> _FakeResponse:
        self.calls_delete.append((url, headers))
        return _FakeResponse()

    def close(self) -> None:
        return None


@dataclass(slots=True)
class _FakeSpan:
    name: str
    start_time_ms: int
    end_time_ms: int


class SimpleFlowClientTests(unittest.TestCase):
    def test_write_chat_message_strips_created_at_ms(self) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]

        client.write_chat_message(
            {
                "agent_id": "agent_1",
                "organization_id": "org_1",
                "run_id": "run_1",
                "chat_id": "chat_1",
                "message_id": "msg_1",
                "role": "assistant",
                "content": {"reply": "ok"},
                "metadata": {},
                "created_at_ms": 123,
                "idempotency_key": "idem_1",
            }
        )

        _, payload, headers = fake_http.calls[-1]
        self.assertNotIn("created_at_ms", payload)
        self.assertEqual(headers.get("Idempotency-Key"), "idem_1")

    def test_write_event_strips_unknown_runtime_fields(self) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]

        client.write_event(
            {
                "agent_id": "agent_1",
                "organization_id": "org_1",
                "run_id": "run_1",
                "type": "runtime.invoke.completed",
                "trace_id": "trace_1",
                "conversation_id": "chat_1",
                "request_id": "req_1",
                "payload": {"status": "ok"},
                "agent_version": "v1",
                "timestamp_ms": 123,
                "idempotency_key": "evt_1",
            }
        )

        _, payload, headers = fake_http.calls[-1]
        self.assertEqual(payload.get("event_type"), "runtime.invoke.completed")
        self.assertNotIn("agent_version", payload)
        self.assertNotIn("timestamp_ms", payload)
        self.assertEqual(headers.get("Idempotency-Key"), "evt_1")

    def test_write_chat_message_from_workflow_result_persists_trace_metadata(
        self,
    ) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        fake_http.registrations_payload = []
        client._client = fake_http  # type: ignore[attr-defined]

        client.write_chat_message_from_workflow_result(
            agent_id="agent_support_v1",
            organization_id="org_1",
            run_id="run_1",
            role="assistant",
            trace_id="92f4be5ae517295005df76967d32984b",
            span_id="span_1",
            tenant_id="tenant_1",
            workflow_result={
                "workflow_id": "email-chat-draft-or-clarify",
                "terminal_node": "generate_email_draft",
                "terminal_output": {"subject": "S", "body": "B"},
                "trace": ["detect_scenario_context", "generate_email_draft"],
                "step_timings": [],
                "llm_node_metrics": {},
                "total_elapsed_ms": 123,
                "events": [
                    {"event_type": "workflow_started", "metadata": {}},
                    {
                        "event_type": "workflow_completed",
                        "metadata": {
                            "nerdstats": {
                                "total_elapsed_ms": 123,
                                "total_tokens": 456,
                            }
                        },
                    },
                ],
            },
        )

        _, payload, _ = fake_http.calls[-1]
        self.assertEqual(payload["role"], "assistant")
        self.assertEqual(
            payload["content"]["workflow"]["workflow_id"], "email-chat-draft-or-clarify"
        )
        self.assertEqual(
            payload["metadata"]["trace_context"]["trace_url"],
            "http://localhost:16686/trace/92f4be5ae517295005df76967d32984b",
        )
        self.assertEqual(payload["metadata"]["event_counts"]["workflow_completed"], 1)
        self.assertEqual(payload["metadata"]["nerdstats"]["total_tokens"], 456)

    def test_write_chat_message_from_workflow_result_uses_custom_trace_base_url(
        self,
    ) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        fake_http.registrations_payload = []
        client._client = fake_http  # type: ignore[attr-defined]

        client.write_chat_message_from_workflow_result(
            agent_id="agent_support_v1",
            organization_id="org_1",
            run_id="run_1",
            role="assistant",
            trace_id="trace_abc",
            trace_ui_base_url="https://jaeger.example",
            workflow_result={"workflow_id": "wf", "terminal_node": "done"},
        )

        _, payload, _ = fake_http.calls[-1]
        self.assertEqual(
            payload["metadata"]["trace_context"]["trace_url"],
            "https://jaeger.example/trace/trace_abc",
        )

    def test_write_event_from_workflow_result_extracts_trace_fields(self) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        fake_http.registrations_payload = []
        client._client = fake_http  # type: ignore[attr-defined]

        client.write_event_from_workflow_result(
            agent_id="agent_support_v1",
            workflow_result={
                "workflow_id": "email-chat-draft-or-clarify",
                "terminal_node": "ask_for_scenario",
                "run_id": "run_123",
                "metadata": {
                    "telemetry": {"trace_id": "trace_123", "sampled": True},
                    "trace": {
                        "tenant": {
                            "conversation_id": "chat_123",
                            "request_id": "req_123",
                            "user_id": "user_123",
                        }
                    },
                },
                "events": [
                    {"event_type": "workflow_started"},
                    {
                        "event_type": "workflow_completed",
                        "metadata": {
                            "nerdstats": {
                                "total_input_tokens": 10,
                                "total_output_tokens": 5,
                                "total_tokens": 15,
                                "step_details": [
                                    {
                                        "model_name": "gpt-5-mini",
                                        "prompt_tokens": 10,
                                        "completion_tokens": 5,
                                        "total_tokens": 15,
                                    }
                                ],
                            }
                        },
                    },
                ],
            },
        )

        _, payload, _ = fake_http.calls[-1]
        self.assertEqual(payload["event_type"], "runtime.workflow.completed")
        self.assertEqual(payload["trace_id"], "trace_123")
        self.assertEqual(payload["conversation_id"], "chat_123")
        self.assertEqual(payload["request_id"], "req_123")
        self.assertEqual(payload["sampled"], True)
        self.assertEqual(payload["user_id"], "user_123")
        self.assertEqual(payload["payload"]["schema_version"], "telemetry-envelope.v1")
        self.assertEqual(payload["payload"]["usage"]["total_tokens"], 15)

    def test_with_telemetry_simpleflow_emits_runtime_event(self) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        fake_http.registrations_payload = []
        client._client = fake_http  # type: ignore[attr-defined]

        telemetry = client.with_telemetry(mode="simpleflow", sample_rate=1.0)
        telemetry.emit_span(
            span=_FakeSpan(name="llm.call", start_time_ms=10, end_time_ms=15),
            agent_id="agent_1",
            run_id="run_1",
            trace_id="trace_1",
        )

        _, payload, _ = fake_http.calls[-1]
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

    def test_auth_and_control_plane_helpers(self) -> None:
        client = SimpleFlowClient(
            base_url="https://api.example", api_token="default_token"
        )
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]

        session = client.create_session("user@example.com", "secret")
        me = client.get_me(auth_token="override_token")
        registrations = client.list_runtime_registrations(
            agent_id="agent_1",
            agent_version="v1",
            auth_token="override_token",
        )
        sessions = client.list_chat_sessions(
            agent_id="agent_1",
            user_id="user_1",
            auth_token="override_token",
        )
        client.delete_current_session(auth_token="override_token")

        self.assertEqual(session["session"]["id"], "sess_1")
        self.assertEqual(me["user_id"], "user_1")
        self.assertEqual(registrations[0]["id"], "reg_1")
        self.assertEqual(sessions[0]["chat_id"], "chat_1")

        post_headers = fake_http.calls[0][2]
        self.assertNotIn("Authorization", post_headers)
        self.assertEqual(
            fake_http.calls_get[0][1]["Authorization"], "Bearer override_token"
        )
        self.assertEqual(
            fake_http.calls_delete[0][1]["Authorization"], "Bearer override_token"
        )

    def test_method_level_auth_override_for_runtime_and_chat_history(self) -> None:
        client = SimpleFlowClient(
            base_url="https://api.example", api_token="default_token"
        )
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]

        client.invoke({"agent_id": "agent_1"}, auth_token="override_token")
        client.list_chat_history_messages(
            agent_id="agent_1",
            chat_id="chat_1",
            user_id="user_1",
            auth_token="override_token",
        )
        client.create_chat_history_message(
            {"agent_id": "agent_1", "chat_id": "chat_1", "user_id": "user_1"},
            auth_token="override_token",
        )
        client.update_chat_history_message(
            message_id="m1",
            agent_id="agent_1",
            chat_id="chat_1",
            user_id="user_1",
            content={},
            metadata={},
            auth_token="override_token",
        )

        self.assertEqual(
            fake_http.calls[0][2]["Authorization"], "Bearer override_token"
        )
        self.assertEqual(
            fake_http.calls_get[0][1]["Authorization"], "Bearer override_token"
        )
        self.assertEqual(
            fake_http.calls[1][2]["Authorization"], "Bearer override_token"
        )
        self.assertEqual(
            fake_http.calls_patch[0][2]["Authorization"], "Bearer override_token"
        )

    def test_runtime_registration_lifecycle_helpers(self) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]

        client.activate_runtime_registration("reg_123")
        client.deactivate_runtime_registration("reg_123")
        validation = client.validate_runtime_registration("reg_123")

        called_urls = [url for (url, _, _) in fake_http.calls]
        self.assertEqual(
            called_urls,
            [
                "https://api.example/v1/runtime/registrations/reg_123/activate",
                "https://api.example/v1/runtime/registrations/reg_123/deactivate",
                "https://api.example/v1/runtime/registrations/reg_123/validate",
            ],
        )
        self.assertEqual(validation["validation_ok"], True)

    def test_ensure_runtime_registration_active_creates_validates_activates(
        self,
    ) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        fake_http.registrations_payload = []
        client._client = fake_http  # type: ignore[attr-defined]

        result = client.ensure_runtime_registration_active(
            registration={"agent_id": "agent_1", "agent_version": "v1"}
        )

        self.assertEqual(result["status"], "active")
        self.assertEqual(result["registration_id"], "reg_created")
        self.assertEqual(result["created"], True)

    def test_error_mapping_for_auth_scope_and_lifecycle(self) -> None:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]

        fake_http.error_by_get_url["https://api.example/v1/me"] = 401
        with self.assertRaises(SimpleFlowAuthenticationError):
            client.get_me(auth_token="bad")

        fake_http.error_by_get_url[
            "https://api.example/v1/runtime/registrations?agent_id=agent_1&agent_version=v1"
        ] = 403
        with self.assertRaises(SimpleFlowAuthorizationError):
            client.list_runtime_registrations(agent_id="agent_1", agent_version="v1")

        fake_http.error_by_post_url[
            "https://api.example/v1/runtime/registrations/reg_123/activate"
        ] = 409
        with self.assertRaises(SimpleFlowLifecycleError):
            client.activate_runtime_registration("reg_123")


class SamplingTests(unittest.TestCase):
    def test_should_sample_is_deterministic(self) -> None:
        first = _should_sample("trace_abc", 0.2)
        second = _should_sample("trace_abc", 0.2)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

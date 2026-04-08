from __future__ import annotations

import unittest
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
import json
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

    def close(self) -> None:
        return None


httpx_stub = types.ModuleType("httpx")
setattr(httpx_stub, "AsyncClient", _NoopHTTPXClient)
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
SimpleFlowAuthenticationError = CLIENT_MODULE.SimpleFlowAuthenticationError
SimpleFlowAuthorizationError = CLIENT_MODULE.SimpleFlowAuthorizationError


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
        self.error_by_post_url: dict[str, int] = {}
        self.error_by_get_url: dict[str, int] = {}

    async def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
        self.calls.append((url, json, headers))
        status_code = self.error_by_post_url.get(url)
        if status_code is not None:
            return _FakeResponse(status_code=status_code, text="denied")
        return _FakeResponse()

    async def get(self, url: str, headers: dict) -> _FakeResponse:
        self.calls_get.append((url, headers))
        status_code = self.error_by_get_url.get(url)
        if status_code is not None:
            return _FakeResponse(status_code=status_code, text="not allowed")
        if "/v1/runtime/chat/sessions" in url:
            return _FakeResponse(
                payload={
                    "sessions": [
                        {
                            "chat_id": "chat_1",
                            "status": "active",
                            "agent_id": "agent_1",
                            "user_id": "user_1",
                        }
                    ]
                }
            )
        if "/v1/runtime/chat/messages/list" in url:
            return _FakeResponse(
                payload={
                    "messages": [
                        {"message_id": "m1", "chat_id": "chat_1", "role": "user"}
                    ]
                }
            )
        return _FakeResponse()

    async def aclose(self) -> None:
        return None


class SimpleFlowClientTests(unittest.TestCase):
    def _new_client(
        self,
        *,
        base_url: str = "https://api.example",
        api_token: str | None = None,
    ) -> tuple[Any, _FakeHTTPClient]:
        kwargs: dict[str, Any] = {"base_url": base_url}
        if api_token is not None:
            kwargs["api_token"] = api_token
        client = SimpleFlowClient(**kwargs)
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]
        return client, fake_http

    def test_write_event_emits_event_to_runtime_endpoint(self) -> None:
        import asyncio

        client, fake_http = self._new_client()

        asyncio.run(
            client.write_event(
                {
                    "event_type": "chat.message.telemetry",
                    "agent_id": "agent_1",
                    "conversation_id": "session_123",
                    "user_id": "user_123",
                    "payload": {
                        "total_tokens": 150,
                        "ttfs": 250,
                    },
                }
            )
        )

        url, payload, _ = fake_http.calls[-1]
        self.assertEqual(url, "https://api.example/v1/runtime/events")
        self.assertEqual(payload["event_type"], "chat.message.telemetry")
        self.assertEqual(payload["agent_id"], "agent_1")
        self.assertEqual(payload["conversation_id"], "session_123")
        self.assertEqual(payload["payload"]["total_tokens"], 150)
        self.assertEqual(payload["payload"]["ttfs"], 250)

    def test_write_event_accepts_auth_token_for_user_authentication(self) -> None:
        import asyncio

        client, fake_http = self._new_client()

        asyncio.run(
            client.write_event(
                {
                    "event_type": "test.event",
                    "agent_id": "agent_1",
                },
                auth_token="user_jwt_token_123",
            )
        )

        _, _, headers = fake_http.calls[-1]
        self.assertEqual(headers.get("Authorization"), "Bearer user_jwt_token_123")

    def test_write_chat_message_emits_message_to_chat_endpoint(self) -> None:
        import asyncio

        client, fake_http = self._new_client()

        asyncio.run(
            client.write_chat_message(
                {
                    "agent_id": "agent_1",
                    "organization_id": "org_123",
                    "user_id": "user_123",
                    "chat_id": "session_123",
                    "role": "user",
                    "content": {"text": "Hello!"},
                    "metadata": {"source": "chat.app"},
                }
            )
        )

        url, payload, _ = fake_http.calls[-1]
        self.assertEqual(url, "https://api.example/v1/runtime/chat/messages")
        self.assertEqual(payload["agent_id"], "agent_1")
        self.assertEqual(payload["chat_id"], "session_123")
        self.assertEqual(payload["role"], "user")
        self.assertEqual(payload["direction"], "outbound")
        self.assertEqual(payload["content"], {"text": "Hello!"})

    def test_write_chat_message_uses_idempotency_key_when_provided(self) -> None:
        import asyncio

        client, fake_http = self._new_client()

        asyncio.run(
            client.write_chat_message(
                {
                    "agent_id": "agent_1",
                    "organization_id": "org_123",
                    "user_id": "user_123",
                    "chat_id": "session_123",
                    "role": "user",
                    "content": {"text": "Hello!"},
                    "idempotency_key": "unique-key-123",
                }
            )
        )

        _, _, headers = fake_http.calls[-1]
        self.assertEqual(headers.get("Idempotency-Key"), "unique-key-123")

    def test_list_chat_sessions_fetches_sessions_with_correct_params(self) -> None:
        import asyncio

        client, fake_http = self._new_client()

        sessions = asyncio.run(
            client.list_chat_sessions(
                agent_id="agent_1",
                user_id="user_123",
                status="active",
                limit=10,
                auth_token="user_token",
            )
        )

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["chat_id"], "chat_1")
        self.assertEqual(sessions[0]["status"], "active")

        url, headers = fake_http.calls_get[-1]
        self.assertIn("/v1/runtime/chat/sessions", url)
        self.assertIn("agent_id=agent_1", url)
        self.assertIn("user_id=user_123", url)
        self.assertIn("status=active", url)
        self.assertIn("limit=10", url)
        self.assertEqual(headers.get("Authorization"), "Bearer user_token")

    def test_list_chat_messages_fetches_messages_with_correct_params(self) -> None:
        import asyncio

        client, fake_http = self._new_client()

        messages = asyncio.run(
            client.list_chat_messages(
                agent_id="agent_1",
                chat_id="session_123",
                user_id="user_123",
                limit=20,
                auth_token="user_token",
            )
        )

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["message_id"], "m1")

        url, headers = fake_http.calls_get[-1]
        self.assertIn("/v1/runtime/chat/messages/list", url)
        self.assertIn("agent_id=agent_1", url)
        self.assertIn("chat_id=session_123", url)
        self.assertIn("user_id=user_123", url)
        self.assertIn("limit=20", url)
        self.assertEqual(headers.get("Authorization"), "Bearer user_token")

    def test_write_message_telemetry_writes_telemetry_for_chat_message(self) -> None:
        import asyncio

        client, fake_http = self._new_client()

        asyncio.run(
            client.write_message_telemetry(
                agent_id="agent_1",
                session_id="session_123",
                metrics={
                    "total_tokens": 150,
                    "ttfs": 250,
                    "prompt_tokens": 50,
                    "completion_tokens": 100,
                    "user_id": "user_123",
                    "run_id": "run_456",
                },
                auth_token="user_jwt_token",
            )
        )

        _, payload, headers = fake_http.calls[-1]
        self.assertEqual(payload["event_type"], "chat.message.telemetry")
        self.assertEqual(payload["agent_id"], "agent_1")
        self.assertEqual(payload["conversation_id"], "session_123")
        self.assertEqual(payload["user_id"], "user_123")
        self.assertEqual(payload["run_id"], "run_456")
        self.assertEqual(payload["payload"]["total_tokens"], 150)
        self.assertEqual(payload["payload"]["ttfs"], 250)
        self.assertEqual(payload["payload"]["prompt_tokens"], 50)
        self.assertEqual(payload["payload"]["completion_tokens"], 100)
        self.assertIsInstance(payload["payload"]["timestamp_ms"], int)
        self.assertEqual(headers.get("Authorization"), "Bearer user_jwt_token")

    def test_authentication_error_raises_simple_flow_authentication_error(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        fake_http.error_by_get_url[
            "https://api.example/v1/runtime/chat/sessions?agent_id=agent_1&user_id=user_1&status=active&limit=50"
        ] = 401

        with self.assertRaises(SimpleFlowAuthenticationError):
            asyncio.run(client.list_chat_sessions(agent_id="agent_1", user_id="user_1"))

    def test_authorization_error_raises_simple_flow_authorization_error(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        fake_http.error_by_get_url[
            "https://api.example/v1/runtime/chat/sessions?agent_id=agent_1&user_id=user_1&status=active&limit=50"
        ] = 403

        with self.assertRaises(SimpleFlowAuthorizationError):
            asyncio.run(client.list_chat_sessions(agent_id="agent_1", user_id="user_1"))

    def test_api_token_used_when_no_auth_token_provided(self) -> None:
        import asyncio

        client, fake_http = self._new_client(api_token="default_machine_token")

        asyncio.run(
            client.write_event(
                {
                    "event_type": "test.event",
                    "agent_id": "agent_1",
                }
            )
        )

        _, _, headers = fake_http.calls[-1]
        self.assertEqual(headers.get("Authorization"), "Bearer default_machine_token")


if __name__ == "__main__":
    unittest.main()

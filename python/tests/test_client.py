from __future__ import annotations

import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any
import sys
import types


class _NoopHTTPXClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout


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
roles_include_any = CLIENT_MODULE.roles_include_any
can_read_chat_user_scope = CLIENT_MODULE.can_read_chat_user_scope


class _FakeResponse:
    def __init__(
        self, status_code: int = 200, payload: dict | None = None, text: str = ""
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text if text else ("" if payload is None else "{}")

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no body")
        return self._payload


class _FakeHTTPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None, dict]] = []
        self.error_by_url: dict[str, int] = {}

    async def request(
        self,
        method: str,
        url: str,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> _FakeResponse:
        hdrs = headers or {}
        self.calls.append((method, url, json, hdrs))
        status = self.error_by_url.get(url)
        if status is not None:
            return _FakeResponse(status_code=status, text="denied")

        if url.endswith("/v1/auth/sessions") and method == "POST":
            return _FakeResponse(
                payload={
                    "access_token": "issued_token",
                    "token_type": "Bearer",
                    "expires_at": "2026-01-01T00:00:00Z",
                    "user": {
                        "id": "u_me",
                        "organization_id": "org",
                        "email": "person@example.com",
                        "full_name": "Person",
                    },
                }
            )
        if url.endswith("/v1/auth/sessions/refresh") and method == "POST":
            return _FakeResponse(
                payload={
                    "access_token": "refreshed_token",
                    "token_type": "Bearer",
                    "expires_at": "2026-01-01T01:00:00Z",
                    "user": {
                        "id": "u_me",
                        "organization_id": "org",
                        "email": "person@example.com",
                        "full_name": "Person",
                    },
                }
            )

        if "/v1/chat/sessions" in url and method == "GET" and "chat_id=" not in url:
            return _FakeResponse(
                payload={
                    "sessions": [
                        {
                            "chat_id": "chat_1",
                            "status": "active",
                            "agent_id": "agent_1",
                            "user_id": "user_1",
                        }
                    ],
                    "page": 2,
                    "limit": 20,
                    "has_more": True,
                }
            )
        if "/v1/chat/sessions" in url and method == "GET" and "chat_id=" in url:
            return _FakeResponse(
                payload={
                    "messages": [
                        {"message_id": "m1", "chat_id": "chat_1", "role": "user"}
                    ]
                }
            )
        if method == "PATCH" and "/v1/chat/sessions/" in url:
            return _FakeResponse(payload={"chat_id": "chat_1", "status": "archived"})
        if method == "GET" and "/v1/chat/messages/" in url and "/output" in url:
            return _FakeResponse(payload={"output": {"workflow_id": "wf_1"}})
        if method == "POST" and "/v1/chat/messages/" in url and "/output" in url:
            return _FakeResponse(
                payload={
                    "message_id": "m1",
                    "chat_id": "chat_1",
                    "output_data": {"workflow_id": "wf_1"},
                }
            )
        if url.endswith("/v1/me"):
            return _FakeResponse(
                payload={
                    "user_id": "u_me",
                    "organization_id": "org",
                    "role": "member",
                }
            )
        if "/api/v1/agents/" in url:
            return _FakeResponse(payload={"ID": "agent_1"})
        return _FakeResponse(payload={})

    async def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
        return await self.request("POST", url, json=json, headers=headers)

    async def aclose(self) -> None:
        return None


class SimpleFlowClientTests(unittest.TestCase):
    def _new_client(self) -> tuple[Any, _FakeHTTPClient]:
        client = SimpleFlowClient(base_url="https://api.example")
        fake_http = _FakeHTTPClient()
        client._client = fake_http  # type: ignore[attr-defined]
        return client, fake_http

    def test_list_chat_sessions_uses_new_endpoint(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        sessions = asyncio.run(
            client.list_chat_sessions(
                agent_id="agent_1",
                user_id="user_1",
                status="active",
                page=2,
                limit=20,
                auth_token="jwt",
            )
        )

        self.assertEqual(sessions[0]["chat_id"], "chat_1")
        method, url, _, headers = fake_http.calls[-1]
        self.assertEqual(method, "GET")
        self.assertIn("/v1/chat/sessions", url)
        self.assertIn("page=2", url)
        self.assertEqual(headers.get("Authorization"), "Bearer jwt")

    def test_list_chat_messages_uses_chat_sessions_query(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        messages = asyncio.run(
            client.list_chat_messages(
                agent_id="agent_1",
                chat_id="chat_1",
                user_id="user_1",
                limit=10,
                auth_token="jwt",
            )
        )
        self.assertEqual(messages[0]["message_id"], "m1")
        _, url, _, _ = fake_http.calls[-1]
        self.assertIn("/v1/chat/sessions", url)
        self.assertIn("chat_id=chat_1", url)

    def test_list_chat_sessions_page_returns_has_more(self) -> None:
        import asyncio

        client, _fake_http = self._new_client()
        page = asyncio.run(
            client.list_chat_sessions_page(
                agent_id="agent_1",
                user_id="user_1",
                page=2,
                limit=20,
                auth_token="jwt",
            )
        )
        self.assertEqual(page.get("page"), 2)
        self.assertEqual(page.get("limit"), 20)
        self.assertEqual(page.get("has_more"), True)

    def test_list_chat_sessions_without_user_id_for_admin_flow(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        sessions = asyncio.run(
            client.list_chat_sessions(
                agent_id="agent_1",
                auth_token="jwt",
            )
        )
        self.assertEqual(sessions[0]["chat_id"], "chat_1")
        _method, url, _payload, _headers = fake_http.calls[-1]
        self.assertNotIn("user_id=", url)

    def test_write_chat_message_uses_telemetry_data(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        asyncio.run(
            client.write_chat_message(
                {
                    "agent_id": "agent_1",
                    "user_id": "user_1",
                    "chat_id": "chat_1",
                    "message_id": "m1",
                    "role": "user",
                    "content": {"text": "hi"},
                    "telemetry_data": {"source": "web"},
                },
                auth_token="jwt",
            )
        )
        method, url, payload, _ = fake_http.calls[-1]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://api.example/v1/chat/sessions")
        self.assertIsNotNone(payload)
        post_payload = payload or {}
        self.assertIn("telemetry_data", post_payload)
        self.assertNotIn("metadata", post_payload)

    def test_write_chat_message_rejects_unknown_top_level_keys(self) -> None:
        import asyncio

        client, _fake_http = self._new_client()
        with self.assertRaisesRegex(ValueError, "unknown keys"):
            asyncio.run(
                client.write_chat_message(
                    {
                        "agent_id": "agent_1",
                        "user_id": "user_1",
                        "chat_id": "chat_1",
                        "message_id": "m1",
                        "role": "assistant",
                        "content": {"text": "hi"},
                        "telemetry_data": {"source": "web"},
                        "unexpected": True,
                    },
                    auth_token="jwt",
                )
            )

    def test_write_chat_message_rejects_output_data_for_non_assistant(self) -> None:
        import asyncio

        client, _fake_http = self._new_client()
        with self.assertRaisesRegex(ValueError, "only allowed when role is assistant"):
            asyncio.run(
                client.write_chat_message(
                    {
                        "agent_id": "agent_1",
                        "user_id": "user_1",
                        "chat_id": "chat_1",
                        "message_id": "m1",
                        "role": "user",
                        "content": {"text": "hi"},
                        "telemetry_data": {"source": "web"},
                        "output_data": {"workflow_id": "wf_1"},
                    },
                    auth_token="jwt",
                )
            )

    def test_create_auth_session_sets_default_token(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        out = asyncio.run(
            client.create_auth_session(
                email="person@example.com",
                password="secret",
            )
        )
        self.assertEqual(out.get("access_token"), "issued_token")
        self.assertEqual(client._api_token, "issued_token")
        method, url, payload, _headers = fake_http.calls[-1]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/v1/auth/sessions"))
        self.assertEqual((payload or {}).get("email"), "person@example.com")

    def test_refresh_auth_session_uses_csrf_header(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        out = asyncio.run(client.refresh_auth_session(csrf_token="csrf_token"))
        self.assertEqual(out.get("access_token"), "refreshed_token")
        self.assertEqual(client._api_token, "refreshed_token")
        method, url, _payload, headers = fake_http.calls[-1]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/v1/auth/sessions/refresh"))
        self.assertEqual(headers.get("X-CSRF-Token"), "csrf_token")

    def test_validate_access_token_uses_me_endpoint(self) -> None:
        import asyncio

        client, _fake_http = self._new_client()
        client._api_token = "issued_token"
        out = asyncio.run(client.validate_access_token())
        self.assertEqual(out.get("user_id"), "u_me")

    def test_build_chat_message_from_simple_agents_result(self) -> None:
        client, _fake_http = self._new_client()
        message = client.build_chat_message_from_simple_agents_result(
            agent_id="agent_1",
            user_id="user_1",
            chat_id="chat_1",
            message_id="m_assistant",
            workflow_result={
                "workflow_id": "wf_invoice",
                "terminal_output": {
                    "label": "finance/invoice",
                    "reason": "looks like invoice",
                    "extra": "dropped",
                },
                "total_input_tokens": 10,
                "total_output_tokens": 5,
                "total_tokens": 15,
                "total_elapsed_ms": 25,
                "outputs": {
                    "node_1": {
                        "output": {
                            "label": "finance/invoice",
                            "reason": "ok",
                            "unknown": "drop",
                        }
                    }
                },
                "events": [{"ignored": True}],
            },
        )
        self.assertEqual(message["role"], "assistant")
        self.assertEqual(message["output_data"]["workflow_id"], "wf_invoice")
        self.assertNotIn("events", message["output_data"])

    def test_write_chat_message_from_simple_agents_result_posts_assistant_message(
        self,
    ) -> None:
        import asyncio

        client, fake_http = self._new_client()
        asyncio.run(
            client.write_chat_message_from_simple_agents_result(
                agent_id="agent_1",
                user_id="user_1",
                chat_id="chat_1",
                message_id="m_assistant",
                workflow_result={
                    "terminal_output": "done",
                    "workflow_id": "wf_1",
                },
                auth_token="jwt",
            )
        )
        method, url, payload, _headers = fake_http.calls[-1]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/v1/chat/sessions"))
        self.assertEqual((payload or {}).get("role"), "assistant")
        self.assertIn("output_data", payload or {})

    def test_update_chat_session_calls_patch(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        out = asyncio.run(
            client.update_chat_session(
                chat_id="chat_1",
                agent_id="agent_1",
                user_id="user_1",
                status="archived",
                auth_token="jwt",
            )
        )
        self.assertEqual(out.get("status"), "archived")
        method, url, payload, _ = fake_http.calls[-1]
        self.assertEqual(method, "PATCH")
        self.assertTrue(url.endswith("/v1/chat/sessions/chat_1"))
        self.assertIsNotNone(payload)
        patch_payload = payload or {}
        self.assertEqual(patch_payload.get("status"), "archived")

    def test_get_chat_message_output(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        out = asyncio.run(
            client.get_chat_message_output(
                message_id="m1",
                agent_id="agent_1",
                chat_id="chat_1",
                user_id="user_1",
                auth_token="jwt",
            )
        )
        self.assertEqual(out.get("output", {}).get("workflow_id"), "wf_1")
        method, url, _payload, _headers = fake_http.calls[-1]
        self.assertEqual(method, "GET")
        self.assertIn("/v1/chat/messages/m1/output", url)

    def test_upsert_chat_message_output(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        out = asyncio.run(
            client.upsert_chat_message_output(
                message_id="m1",
                agent_id="agent_1",
                chat_id="chat_1",
                user_id="user_1",
                output_data={"workflow_id": "wf_1", "events": ["drop"]},
                auth_token="jwt",
            )
        )
        self.assertEqual(out.get("chat_id"), "chat_1")
        method, url, payload, _headers = fake_http.calls[-1]
        self.assertEqual(method, "POST")
        self.assertIn("/v1/chat/messages/m1/output", url)
        self.assertNotIn("events", (payload or {}).get("output_data", {}))

    def test_list_chat_sessions_raises_auth_error(self) -> None:
        import asyncio

        client, fake_http = self._new_client()
        fake_http.error_by_url[
            "https://api.example/v1/chat/sessions?agent_id=agent_1&user_id=user_1&page=1&limit=20"
        ] = 401
        with self.assertRaises(SimpleFlowAuthenticationError):
            asyncio.run(client.list_chat_sessions(agent_id="agent_1", user_id="user_1"))


class AuthzHelpersTests(unittest.TestCase):
    def test_roles_include_any(self) -> None:
        self.assertTrue(roles_include_any(["member", "admin"], ["admin"]))
        self.assertFalse(roles_include_any(["member"], ["admin"]))

    def test_can_read_chat_user_scope(self) -> None:
        self.assertTrue(
            can_read_chat_user_scope(
                roles=["member"], principal_user_id="u1", target_user_id="u1"
            )
        )
        self.assertFalse(
            can_read_chat_user_scope(
                roles=["member"], principal_user_id="u1", target_user_id="u2"
            )
        )
        self.assertTrue(
            can_read_chat_user_scope(
                roles=["admin"], principal_user_id="u1", target_user_id="u2"
            )
        )
        self.assertFalse(
            can_read_chat_user_scope(
                roles=["member"], principal_user_id="u1", target_user_id=""
            )
        )
        self.assertTrue(
            can_read_chat_user_scope(
                roles=["super_admin"], principal_user_id="u1", target_user_id=""
            )
        )


if __name__ == "__main__":
    unittest.main()

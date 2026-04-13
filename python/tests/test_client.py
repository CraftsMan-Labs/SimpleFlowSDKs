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
        if url.endswith("/v1/me"):
            return _FakeResponse(
                payload={
                    "user_id": "u_me",
                    "organization_id": "org",
                    "roles": ["member"],
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

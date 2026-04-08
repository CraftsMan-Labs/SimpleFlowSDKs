from __future__ import annotations

from dataclasses import is_dataclass, fields
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx

if TYPE_CHECKING:
    from .response_models import ChatSession


class SimpleFlowRequestError(RuntimeError):
    def __init__(self, *, status_code: int, detail: str, path: str) -> None:
        super().__init__(
            f"simpleflow sdk request error: status={status_code} path={path} detail={detail}"
        )
        self.status_code = status_code
        self.detail = detail
        self.path = path


class SimpleFlowAuthenticationError(SimpleFlowRequestError):
    pass


class SimpleFlowAuthorizationError(SimpleFlowRequestError):
    pass


ALLOWED_EVENT_KEYS = frozenset(
    {
        "agent_id",
        "organization_id",
        "user_id",
        "run_id",
        "event_type",
        "trace_id",
        "conversation_id",
        "request_id",
        "sampled",
        "payload",
    }
)

ALLOWED_CHAT_MESSAGE_KEYS = frozenset(
    {
        "agent_id",
        "organization_id",
        "run_id",
        "chat_id",
        "message_id",
        "role",
        "direction",
        "content",
        "metadata",
    }
)


def _normalize_payload(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if is_dataclass(payload):
        return {field.name: getattr(payload, field.name) for field in fields(payload)}
    raise TypeError(
        "simpleflow sdk payload error: payload must be a dataclass, dict, or None"
    )


def _normalize_chat_session(value: dict[str, Any]) -> ChatSession:
    result: dict[str, Any] = {}
    if isinstance(value.get("chat_id"), str):
        result["chat_id"] = value["chat_id"]
    if isinstance(value.get("status"), str):
        result["status"] = value["status"]
    if isinstance(value.get("agent_id"), str):
        result["agent_id"] = value["agent_id"]
    if isinstance(value.get("user_id"), str):
        result["user_id"] = value["user_id"]
    metadata = value.get("metadata")
    if isinstance(metadata, dict):
        result["metadata"] = metadata
    return result  # type: ignore[return-value]


class SimpleFlowClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_token: str = "",
        timeout_ms: float = 10000,
        runtime_events_path: str = "/v1/runtime/events",
        runtime_chat_messages_path: str = "/v1/runtime/chat/messages",
        runtime_chat_sessions_path: str = "/v1/runtime/chat/sessions",
        runtime_chat_messages_list_path: str = "/v1/runtime/chat/messages/list",
    ) -> None:
        if not str(base_url or "").strip():
            raise ValueError("simpleflow sdk config error: base_url is required")
        self._base_url = str(base_url).rstrip("/")
        self._api_token = str(api_token or "").strip()
        self._timeout_ms = float(timeout_ms or 10000)
        self._runtime_events_path = runtime_events_path
        self._runtime_chat_messages_path = runtime_chat_messages_path
        self._runtime_chat_sessions_path = runtime_chat_sessions_path
        self._runtime_chat_messages_list_path = runtime_chat_messages_list_path
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout_ms / 1000)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _path_with_query(self, path: str, query: dict[str, Any]) -> str:
        params: dict[str, str] = {}
        for key, value in query.items():
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            params[key] = text
        if params:
            return f"{path}?{urlencode(params)}"
        return path

    def _authorization_headers(self, auth_token: str | None = None) -> dict[str, str]:
        token = ""
        if isinstance(auth_token, str):
            token = auth_token.strip()
        else:
            token = self._api_token
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    async def _post(
        self,
        path: str,
        payload: Any,
        auth_token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        client = self._get_client()
        headers = {**self._authorization_headers(auth_token), **(extra_headers or {})}
        url = f"{self._base_url}{path}"
        response = await client.post(
            url, json=_normalize_payload(payload), headers=headers
        )
        if response.status_code < 200 or response.status_code >= 300:
            self._raise_request_error(
                path=path, status_code=response.status_code, body=response.text
            )
        if not response.text.strip():
            return {}
        data = response.json()
        if not isinstance(data, dict):
            raise SimpleFlowRequestError(
                status_code=502, detail="expected JSON object response body", path=path
            )
        return data

    async def _get(self, path: str, auth_token: str | None = None) -> dict[str, Any]:
        client = self._get_client()
        headers = self._authorization_headers(auth_token)
        url = f"{self._base_url}{path}"
        response = await client.get(url, headers=headers)
        if response.status_code < 200 or response.status_code >= 300:
            self._raise_request_error(
                path=path, status_code=response.status_code, body=response.text
            )
        if not response.text.strip():
            return {}
        data = response.json()
        if not isinstance(data, dict):
            raise SimpleFlowRequestError(
                status_code=502, detail="expected JSON object response body", path=path
            )
        return data

    def _raise_request_error(self, *, path: str, status_code: int, body: str) -> None:
        detail = str(body or "").strip() or "request failed"
        if status_code == 401:
            raise SimpleFlowAuthenticationError(
                status_code=status_code, detail=detail, path=path
            )
        if status_code == 403:
            raise SimpleFlowAuthorizationError(
                status_code=status_code, detail=detail, path=path
            )
        raise SimpleFlowRequestError(status_code=status_code, detail=detail, path=path)

    async def list_chat_sessions(
        self,
        *,
        agent_id: str,
        user_id: str,
        status: str = "active",
        limit: int = 50,
        auth_token: str | None = None,
    ) -> list[dict[str, Any]]:
        sessions_typed = await self.list_chat_sessions_typed(
            agent_id=agent_id,
            user_id=user_id,
            status=status,
            limit=limit,
            auth_token=auth_token,
        )
        return [dict(session) for session in sessions_typed]

    async def list_chat_sessions_typed(
        self,
        *,
        agent_id: str,
        user_id: str,
        status: str = "active",
        limit: int = 50,
        auth_token: str | None = None,
    ) -> list[ChatSession]:
        path = self._path_with_query(
            self._runtime_chat_sessions_path,
            {
                "agent_id": agent_id,
                "user_id": user_id,
                "status": status,
                "limit": limit,
            },
        )
        response = await self._get(path, auth_token=auth_token)
        sessions = response.get("sessions")
        if not isinstance(sessions, list):
            return []
        return [
            _normalize_chat_session(item) for item in sessions if isinstance(item, dict)
        ]

    async def list_chat_messages(
        self,
        *,
        agent_id: str,
        chat_id: str,
        user_id: str,
        limit: int = 50,
        auth_token: str | None = None,
    ) -> list[dict[str, Any]]:
        path = self._path_with_query(
            self._runtime_chat_messages_list_path,
            {
                "agent_id": agent_id,
                "chat_id": chat_id,
                "user_id": user_id,
                "limit": limit,
            },
        )
        response = await self._get(path, auth_token=auth_token)
        messages = response.get("messages")
        if isinstance(messages, list):
            return [item for item in messages if isinstance(item, dict)]
        return []

    async def write_chat_message(
        self, message: Any, auth_token: str | None = None
    ) -> None:
        body = _normalize_payload(message)
        idempotency_key = str(body.pop("idempotency_key", "")).strip()
        body.pop("created_at_ms", None)
        body = {
            key: value
            for key, value in body.items()
            if key in ALLOWED_CHAT_MESSAGE_KEYS
        }
        direction = str(body.get("direction", "")).strip()
        if direction == "":
            body["direction"] = "outbound"
        if body.get("content") is None:
            body["content"] = {}
        if body.get("metadata") is None:
            body["metadata"] = {}
        headers: dict[str, str] = {}
        if idempotency_key != "":
            headers["Idempotency-Key"] = idempotency_key
        await self._post(
            self._runtime_chat_messages_path,
            body,
            auth_token=auth_token,
            extra_headers=headers,
        )

    async def write_event(self, event: Any, auth_token: str | None = None) -> None:
        body = _normalize_payload(event)
        event_type = str(body.get("event_type", "")).strip()
        if event_type == "":
            event_type = str(body.get("type", "")).strip()
        body["event_type"] = event_type
        body.pop("type", None)
        idempotency_key = str(body.pop("idempotency_key", "")).strip()
        body = {key: value for key, value in body.items() if key in ALLOWED_EVENT_KEYS}
        headers: dict[str, str] = {}
        if idempotency_key != "":
            headers["Idempotency-Key"] = idempotency_key
        await self._post(
            self._runtime_events_path,
            body,
            auth_token=auth_token,
            extra_headers=headers,
        )

    async def write_message_telemetry(
        self,
        *,
        agent_id: str,
        session_id: str,
        metrics: dict[str, Any],
        auth_token: str | None = None,
    ) -> None:
        """Write telemetry metrics for a chat message.

        Args:
            agent_id: Agent identifier
            session_id: Chat session ID (conversation_id)
            metrics: Telemetry metrics dictionary containing:
                - total_tokens: Total tokens used (required)
                - ttfs: Time to first token in milliseconds (required)
                - prompt_tokens: Input tokens (optional)
                - completion_tokens: Output tokens (optional)
                - user_id: User identifier (optional)
                - run_id: Run identifier (optional)
            auth_token: User's JWT bearer token
        """
        await self.write_event(
            {
                "event_type": "chat.message.telemetry",
                "agent_id": agent_id,
                "conversation_id": session_id,
                "user_id": metrics.get("user_id", ""),
                "run_id": metrics.get("run_id", ""),
                "payload": {
                    "total_tokens": metrics.get("total_tokens"),
                    "ttfs": metrics.get("ttfs"),
                    "prompt_tokens": metrics.get("prompt_tokens"),
                    "completion_tokens": metrics.get("completion_tokens"),
                    "timestamp_ms": int(time.time() * 1000),
                },
            },
            auth_token=auth_token,
        )

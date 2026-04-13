from __future__ import annotations

from dataclasses import is_dataclass, fields
import json
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Iterable, Sequence
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


def roles_include_any(user_roles: Sequence[str], required: Iterable[str]) -> bool:
    """Return True if any role in ``required`` is present in ``user_roles`` (exact string match)."""
    have = {str(r).strip() for r in user_roles if str(r).strip() != ""}
    for r in required:
        if str(r).strip() in have:
            return True
    return False


def can_read_chat_user_scope(
    *,
    roles: Sequence[str],
    principal_user_id: str,
    target_user_id: str | None,
) -> bool:
    """Mirror control-plane chat read scope (see ``requireChatReadScope`` / ``requireChatUserScope``).

    - Empty ``target_user_id``: allowed only for ``admin`` or ``super_admin``.
    - Non-empty ``target_user_id``: admins may read any user; others only their own ``principal_user_id``.
    """
    role_set = {str(r).strip() for r in roles if str(r).strip() != ""}
    privileged = "admin" in role_set or "super_admin" in role_set
    target = str(target_user_id or "").strip()
    if target == "":
        return privileged
    if privileged:
        return True
    return str(principal_user_id or "").strip() == target


ALLOWED_CHAT_MESSAGE_KEYS = frozenset(
    {
        "agent_id",
        "user_id",
        "chat_id",
        "message_id",
        "role",
        "content",
        "telemetry_data",
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


def _safe_message_id_suffix(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip())
    normalized = normalized.strip("_")
    if normalized == "":
        return "step"
    return normalized


def _stringify_content(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except TypeError:
        return str(value)


class SimpleFlowClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_token: str = "",
        oauth_client_id: str = "",
        oauth_client_secret: str = "",
        oauth_token_path: str = "/v1/oauth/token",
        timeout_ms: float = 10000,
        chat_sessions_path: str = "/v1/chat/sessions",
        me_path: str = "/v1/me",
    ) -> None:
        if not str(base_url or "").strip():
            raise ValueError("simpleflow sdk config error: base_url is required")
        self._base_url = str(base_url).rstrip("/")
        self._api_token = str(api_token or "").strip()
        self._oauth_client_id = str(oauth_client_id or "").strip()
        self._oauth_client_secret = str(oauth_client_secret or "").strip()
        self._oauth_token_path = str(oauth_token_path or "/v1/oauth/token").strip()
        self._timeout_ms = float(timeout_ms or 10000)
        self._chat_sessions_path = str(
            chat_sessions_path or "/v1/chat/sessions"
        ).strip()
        self._me_path = str(me_path or "/v1/me").strip() or "/v1/me"
        self._oauth_access_token = ""
        self._oauth_access_token_expires_at: datetime | None = None
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

    async def _authorization_headers(
        self, auth_token: str | None = None, force_oauth: bool = False
    ) -> tuple[dict[str, str], str]:
        token = ""
        source = "none"
        if isinstance(auth_token, str):
            token = auth_token.strip()
            if token != "":
                source = "explicit"
        elif not force_oauth:
            token = self._api_token
            if token != "":
                source = "api_token"
        if token == "":
            token = await self._oauth_access_token_for_machine_credentials()
            if token != "":
                source = "oauth_machine"
        if token:
            return {"Authorization": f"Bearer {token}"}, source
        return {}, source

    async def _oauth_access_token_for_machine_credentials(self) -> str:
        if self._oauth_client_id == "" or self._oauth_client_secret == "":
            return ""
        if (
            self._oauth_access_token != ""
            and self._oauth_access_token_expires_at is not None
        ):
            if datetime.now(timezone.utc) < self._oauth_access_token_expires_at:
                return self._oauth_access_token

        client = self._get_client()
        path = (
            self._oauth_token_path
            if self._oauth_token_path.startswith("/")
            else f"/{self._oauth_token_path}"
        )
        url = f"{self._base_url}{path}"
        response = await client.post(
            url,
            json={
                "grant_type": "client_credentials",
                "client_id": self._oauth_client_id,
                "client_secret": self._oauth_client_secret,
            },
            headers={},
        )
        if response.status_code < 200 or response.status_code >= 300:
            self._raise_request_error(
                path=path, status_code=response.status_code, body=response.text
            )
        if not response.text.strip():
            raise SimpleFlowRequestError(
                status_code=502,
                detail="expected JSON object response body",
                path=path,
            )
        data = response.json()
        if not isinstance(data, dict):
            raise SimpleFlowRequestError(
                status_code=502, detail="expected JSON object response body", path=path
            )

        access_token = str(data.get("access_token", "")).strip()
        if access_token == "":
            raise SimpleFlowRequestError(
                status_code=502,
                detail="missing access_token in oauth response",
                path=path,
            )
        expires_in_raw = data.get("expires_in", 0)
        try:
            expires_in = int(expires_in_raw)
        except (TypeError, ValueError):
            expires_in = 0
        refresh_skew = 5
        expires_delta = max(0, expires_in - refresh_skew)
        self._oauth_access_token = access_token
        self._oauth_access_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=expires_delta
        )
        return self._oauth_access_token

    async def _post(
        self,
        path: str,
        payload: Any,
        auth_token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            method="POST",
            path=path,
            payload=payload,
            auth_token=auth_token,
            extra_headers=extra_headers,
        )

    async def _get(self, path: str, auth_token: str | None = None) -> dict[str, Any]:
        return await self._request(method="GET", path=path, auth_token=auth_token)

    async def _request(
        self,
        *,
        method: str,
        path: str,
        payload: Any | None = None,
        auth_token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        client = self._get_client()
        auth_headers, auth_source = await self._authorization_headers(auth_token)
        headers = {**auth_headers, **(extra_headers or {})}
        url = f"{self._base_url}{path}"
        normalized_payload = (
            _normalize_payload(payload) if payload is not None else None
        )
        response = await client.request(
            method,
            url,
            json=normalized_payload,
            headers=headers,
        )
        if (
            response.status_code == 401
            and auth_token is None
            and auth_source == "api_token"
            and self._oauth_client_id != ""
            and self._oauth_client_secret != ""
        ):
            oauth_headers, _ = await self._authorization_headers(
                auth_token, force_oauth=True
            )
            headers = {**oauth_headers, **(extra_headers or {})}
            response = await client.request(
                method,
                url,
                json=normalized_payload,
                headers=headers,
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

    async def fetch_current_user(self, *, auth_token: str) -> dict[str, Any]:
        """Load the current user from ``GET /v1/me`` (org roles include ``member``, ``admin``, ``super_admin``)."""
        token = str(auth_token or "").strip()
        if token == "":
            raise ValueError("simpleflow sdk config error: auth_token is required")
        path = self._me_path if self._me_path.startswith("/") else f"/{self._me_path}"
        return await self._get(path, auth_token=token)

    async def fetch_agent(self, *, agent_id: str, auth_token: str) -> dict[str, Any]:
        """Load an agent by id; ``403`` means the user lacks read access to this agent."""
        token = str(auth_token or "").strip()
        if token == "":
            raise ValueError("simpleflow sdk config error: auth_token is required")
        aid = str(agent_id or "").strip()
        if aid == "":
            raise ValueError("simpleflow sdk config error: agent_id is required")
        path = f"/api/v1/agents/{aid}"
        return await self._get(path, auth_token=token)

    async def authorize_runtime_chat_read(
        self,
        *,
        auth_token: str,
        agent_id: str,
        chat_user_id: str | None = None,
    ) -> dict[str, Any]:
        """Validate user session, chat read scope, and agent read access before chat API calls.

        Returns ``{"me": ..., "agent": ...}`` from ``/v1/me`` and ``GET /api/v1/agents/{agent_id}``.
        """
        me = await self.fetch_current_user(auth_token=auth_token)
        roles_raw = me.get("roles")
        roles: list[str] = (
            [str(x) for x in roles_raw if str(x).strip() != ""]
            if isinstance(roles_raw, list)
            else []
        )
        uid = str(me.get("user_id", "")).strip()
        if not can_read_chat_user_scope(
            roles=roles,
            principal_user_id=uid,
            target_user_id=chat_user_id,
        ):
            raise SimpleFlowAuthorizationError(
                status_code=403,
                detail="chat read scope denied for this principal and target user_id",
                path="/v1/chat/sessions",
            )
        agent = await self.fetch_agent(agent_id=agent_id, auth_token=auth_token)
        return {"me": me, "agent": agent}

    async def list_chat_sessions(
        self,
        *,
        agent_id: str,
        user_id: str,
        status: str | None = None,
        page: int = 1,
        limit: int = 20,
        auth_token: str | None = None,
    ) -> list[dict[str, Any]]:
        sessions_typed = await self.list_chat_sessions_typed(
            agent_id=agent_id,
            user_id=user_id,
            status=status,
            page=page,
            limit=limit,
            auth_token=auth_token,
        )
        return [dict(session) for session in sessions_typed]

    async def list_chat_sessions_typed(
        self,
        *,
        agent_id: str,
        user_id: str,
        status: str | None = None,
        page: int = 1,
        limit: int = 20,
        auth_token: str | None = None,
    ) -> list[ChatSession]:
        path = self._path_with_query(
            self._chat_sessions_path,
            {
                "agent_id": agent_id,
                "user_id": user_id,
                "status": status,
                "page": page,
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
        limit: int = 20,
        auth_token: str | None = None,
    ) -> list[dict[str, Any]]:
        path = self._path_with_query(
            self._chat_sessions_path,
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
    ) -> dict[str, Any]:
        body = _normalize_payload(message)
        idempotency_key = str(body.pop("idempotency_key", "")).strip()
        body = {
            key: value
            for key, value in body.items()
            if key in ALLOWED_CHAT_MESSAGE_KEYS
        }
        required_keys = ["agent_id", "user_id", "chat_id", "message_id", "role"]
        missing = [key for key in required_keys if str(body.get(key, "")).strip() == ""]
        if missing:
            raise ValueError(
                f"simpleflow sdk payload error: missing required keys: {', '.join(missing)}"
            )
        if body.get("content") is None:
            body["content"] = {}
        if body.get("telemetry_data") is None:
            body["telemetry_data"] = {}
        headers: dict[str, str] = {}
        if idempotency_key != "":
            headers["Idempotency-Key"] = idempotency_key
        return await self._post(
            self._chat_sessions_path,
            body,
            auth_token=auth_token,
            extra_headers=headers,
        )

    async def update_chat_session(
        self,
        *,
        chat_id: str,
        agent_id: str,
        user_id: str,
        title: str | None = None,
        status: str | None = None,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        trimmed_chat_id = str(chat_id or "").strip()
        if trimmed_chat_id == "":
            raise ValueError("simpleflow sdk config error: chat_id is required")
        path = f"{self._chat_sessions_path}/{trimmed_chat_id}"
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "user_id": user_id,
        }
        if title is not None:
            payload["title"] = title
        if status is not None:
            payload["status"] = status
        return await self._request(
            method="PATCH",
            path=path,
            payload=payload,
            auth_token=auth_token,
        )

    def chat_messages_from_workflow_result(
        self,
        *,
        agent_id: str,
        user_id: str,
        chat_id: str,
        workflow_result: Any,
        role: str = "assistant",
        include_node_outputs: bool = True,
        include_terminal_output: bool = True,
        telemetry_data: dict[str, Any] | None = None,
        message_id_prefix: str = "wf",
    ) -> list[dict[str, Any]]:
        payload = _normalize_payload(workflow_result)
        base_telemetry: dict[str, Any] = {}
        if isinstance(telemetry_data, dict):
            base_telemetry = dict(telemetry_data)

        messages: list[dict[str, Any]] = []
        counter = 1

        outputs = payload.get("outputs")
        trace = payload.get("trace")
        terminal_node = str(payload.get("terminal_node", "")).strip()

        if include_node_outputs and isinstance(outputs, dict):
            ordered_nodes: list[str] = []
            if isinstance(trace, list):
                for item in trace:
                    if isinstance(item, str) and item in outputs:
                        ordered_nodes.append(item)
            if not ordered_nodes:
                ordered_nodes = [key for key in outputs.keys() if isinstance(key, str)]

            for node_id in ordered_nodes:
                node_payload = outputs.get(node_id)
                node_output = node_payload
                if isinstance(node_payload, dict) and "output" in node_payload:
                    node_output = node_payload.get("output")
                message_telemetry = {
                    **base_telemetry,
                    "kind": "intermediate_step",
                    "node_id": node_id,
                    "terminal": node_id == terminal_node,
                }
                messages.append(
                    {
                        "agent_id": agent_id,
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "message_id": (
                            f"{message_id_prefix}_{counter}_{_safe_message_id_suffix(node_id)}"
                        ),
                        "role": role,
                        "content": {
                            "text": _stringify_content(node_output),
                            "node_id": node_id,
                        },
                        "telemetry_data": message_telemetry,
                    }
                )
                counter += 1

        if include_terminal_output and payload.get("terminal_output") is not None:
            message_telemetry = {
                **base_telemetry,
                "kind": "final_answer",
                "node_id": terminal_node,
            }
            messages.append(
                {
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "message_id": (
                        f"{message_id_prefix}_{counter}_{_safe_message_id_suffix(terminal_node or 'final')}"
                    ),
                    "role": role,
                    "content": {
                        "text": _stringify_content(payload.get("terminal_output"))
                    },
                    "telemetry_data": message_telemetry,
                }
            )

        return messages

    async def write_chat_messages_from_workflow_result(
        self,
        *,
        agent_id: str,
        user_id: str,
        chat_id: str,
        workflow_result: Any,
        role: str = "assistant",
        include_node_outputs: bool = True,
        include_terminal_output: bool = True,
        telemetry_data: dict[str, Any] | None = None,
        message_id_prefix: str = "wf",
        auth_token: str | None = None,
    ) -> list[dict[str, Any]]:
        messages = self.chat_messages_from_workflow_result(
            agent_id=agent_id,
            user_id=user_id,
            chat_id=chat_id,
            workflow_result=workflow_result,
            role=role,
            include_node_outputs=include_node_outputs,
            include_terminal_output=include_terminal_output,
            telemetry_data=telemetry_data,
            message_id_prefix=message_id_prefix,
        )
        for message in messages:
            await self.write_chat_message(message, auth_token=auth_token)
        return messages

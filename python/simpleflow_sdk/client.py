from __future__ import annotations

from dataclasses import is_dataclass, fields
import json
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Iterable, Sequence
from urllib.parse import quote, urlencode

import httpx

if TYPE_CHECKING:
    from .response_models import (
        AuthTokenResponse,
        ChatSession,
        ChatSessionsResponse,
        MessageOutputResponse,
        PrincipalResponse,
    )


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
        "output_data",
    }
)

VALID_CHAT_ROLES = frozenset({"system", "user", "assistant", "tool"})

_CONTENT_ALLOWED_KEYS = frozenset(
    {"text", "title", "message", "prompt", "parts", "messages"}
)
_TELEMETRY_ALLOWED_KEYS = frozenset(
    {
        "source",
        "event_type",
        "client_timestamp",
        "latency_ms",
        "model",
        "tokens",
        "tags",
    }
)
_TELEMETRY_TOKEN_ALLOWED_KEYS = frozenset({"prompt", "completion", "total"})
_STRUCTURED_OUTPUT_ALLOWED_KEYS = frozenset(
    {
        "domain",
        "finance_subtype",
        "company_name",
        "label",
        "reason",
        "stakeholder_name",
        "subtype",
        "top_level_category",
    }
)


def _as_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value.is_integer():
        iv = int(value)
        return iv if iv >= 0 else None
    return None


def _as_non_negative_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        fv = float(value)
        return fv if fv >= 0 else None
    return None


def _sanitize_structured_output(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    out: dict[str, str] = {}
    for key in _STRUCTURED_OUTPUT_ALLOWED_KEYS:
        raw = value.get(key)
        if isinstance(raw, str) and raw.strip() != "":
            out[key] = raw
    return out if out else None


def _sanitize_content(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, Any] = {}
    for key in _CONTENT_ALLOWED_KEYS:
        if key in value:
            out[key] = value[key]
    return out


def _sanitize_telemetry_data(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, Any] = {}
    for key in _TELEMETRY_ALLOWED_KEYS:
        if key in value:
            out[key] = value[key]

    tokens_raw = out.get("tokens")
    if isinstance(tokens_raw, dict):
        tokens: dict[str, int] = {}
        for key in _TELEMETRY_TOKEN_ALLOWED_KEYS:
            parsed = _as_non_negative_int(tokens_raw.get(key))
            if parsed is not None:
                tokens[key] = parsed
        out["tokens"] = tokens
    elif "tokens" in out:
        out.pop("tokens")

    latency = _as_non_negative_int(out.get("latency_ms"))
    if latency is None:
        out.pop("latency_ms", None)
    else:
        out["latency_ms"] = latency

    tags = out.get("tags")
    if isinstance(tags, list):
        out["tags"] = [str(item) for item in tags if str(item).strip() != ""]
    elif "tags" in out:
        out.pop("tags")

    return out


def _sanitize_message_output_data(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    out: dict[str, Any] = {}

    for key in ("workflow_id", "trace_id", "entry_node", "terminal_node"):
        raw = value.get(key)
        if isinstance(raw, str) and raw.strip() != "":
            out[key] = raw

    trace = value.get("trace")
    if isinstance(trace, list):
        out["trace"] = [
            str(item) for item in trace if isinstance(item, str) and item.strip() != ""
        ]

    step_timings_raw = value.get("step_timings")
    if isinstance(step_timings_raw, list):
        step_timings: list[dict[str, Any]] = []
        for item in step_timings_raw:
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("node_id", "")).strip()
            if node_id == "":
                continue
            timing: dict[str, Any] = {"node_id": node_id}
            node_kind = item.get("node_kind")
            if isinstance(node_kind, str) and node_kind.strip() != "":
                timing["node_kind"] = node_kind
            model_name = item.get("model_name")
            if isinstance(model_name, str) and model_name.strip() != "":
                timing["model_name"] = model_name
            for metric_key in (
                "completion_tokens",
                "elapsed_ms",
                "prompt_tokens",
                "reasoning_tokens",
                "total_tokens",
            ):
                parsed = _as_non_negative_int(item.get(metric_key))
                if parsed is not None:
                    timing[metric_key] = parsed
            tps = _as_non_negative_float(item.get("tokens_per_second"))
            if tps is not None:
                timing["tokens_per_second"] = tps
            step_timings.append(timing)
        out["step_timings"] = step_timings

    llm_node_metrics_raw = value.get("llm_node_metrics")
    if isinstance(llm_node_metrics_raw, dict):
        llm_node_metrics: dict[str, dict[str, Any]] = {}
        for node_id, metric_value in llm_node_metrics_raw.items():
            key = str(node_id).strip()
            if key == "" or not isinstance(metric_value, dict):
                continue
            metric: dict[str, Any] = {}
            for metric_key in (
                "completion_tokens",
                "elapsed_ms",
                "prompt_tokens",
                "reasoning_tokens",
                "total_tokens",
            ):
                parsed = _as_non_negative_int(metric_value.get(metric_key))
                if parsed is not None:
                    metric[metric_key] = parsed
            tps = _as_non_negative_float(metric_value.get("tokens_per_second"))
            if tps is not None:
                metric["tokens_per_second"] = tps
            llm_node_metrics[key] = metric
        out["llm_node_metrics"] = llm_node_metrics

    llm_node_models_raw = value.get("llm_node_models")
    if isinstance(llm_node_models_raw, dict):
        llm_node_models: dict[str, str] = {}
        for node_id, model in llm_node_models_raw.items():
            key = str(node_id).strip()
            model_name = str(model).strip() if isinstance(model, str) else ""
            if key != "" and model_name != "":
                llm_node_models[key] = model_name
        out["llm_node_models"] = llm_node_models

    outputs_raw = value.get("outputs")
    if isinstance(outputs_raw, dict):
        outputs: dict[str, dict[str, Any]] = {}
        for node_id, raw_output in outputs_raw.items():
            key = str(node_id).strip()
            if key == "":
                continue
            source = raw_output
            if isinstance(raw_output, dict) and "output" in raw_output:
                source = raw_output.get("output")
            if isinstance(source, str):
                outputs[key] = {"output": source}
                continue
            structured = _sanitize_structured_output(source)
            if structured is not None:
                outputs[key] = {"output": structured}
                continue
            if source is not None:
                outputs[key] = {"output": _stringify_content(source)}
        out["outputs"] = outputs

    metadata_raw = value.get("metadata")
    if isinstance(metadata_raw, dict):
        metadata: dict[str, Any] = {}
        telemetry_raw = metadata_raw.get("telemetry")
        if isinstance(telemetry_raw, dict):
            telemetry: dict[str, Any] = {}
            for key in ("enabled", "multi_tenant", "nerdstats", "sampled"):
                bool_value = telemetry_raw.get(key)
                if isinstance(bool_value, bool):
                    telemetry[key] = bool_value
            for key in (
                "payload_mode",
                "tool_trace_mode",
                "trace_id",
                "trace_id_source",
            ):
                str_value = telemetry_raw.get(key)
                if isinstance(str_value, str) and str_value.strip() != "":
                    telemetry[key] = str_value
            retention_days = _as_non_negative_int(telemetry_raw.get("retention_days"))
            if retention_days is not None:
                telemetry["retention_days"] = retention_days
            sample_rate = _as_non_negative_float(telemetry_raw.get("sample_rate"))
            if sample_rate is not None:
                telemetry["sample_rate"] = sample_rate
            metadata["telemetry"] = telemetry

        trace_raw = metadata_raw.get("trace")
        if isinstance(trace_raw, dict):
            trace_data: dict[str, Any] = {}
            tenant_raw = trace_raw.get("tenant")
            if isinstance(tenant_raw, dict):
                tenant: dict[str, Any] = {}
                for key in (
                    "conversation_id",
                    "request_id",
                    "run_id",
                    "user_id",
                    "workspace_id",
                ):
                    raw_value = tenant_raw.get(key)
                    if raw_value is None:
                        tenant[key] = None
                    elif isinstance(raw_value, str):
                        tenant[key] = raw_value
                trace_data["tenant"] = tenant
            metadata["trace"] = trace_data

        out["metadata"] = metadata

    terminal_output = _sanitize_structured_output(value.get("terminal_output"))
    if terminal_output is not None:
        out["terminal_output"] = terminal_output

    for key in (
        "total_elapsed_ms",
        "total_input_tokens",
        "total_output_tokens",
        "total_reasoning_tokens",
        "total_tokens",
        "ttft_ms",
    ):
        parsed = _as_non_negative_int(value.get(key))
        if parsed is not None:
            out[key] = parsed

    tps = _as_non_negative_float(value.get("tokens_per_second"))
    if tps is not None:
        out["tokens_per_second"] = tps

    return out


def _build_telemetry_data_from_workflow_result(
    workflow_result: dict[str, Any],
    telemetry_data: dict[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "source": "simple-agents",
        "event_type": "assistant.reply",
    }
    latency = _as_non_negative_int(workflow_result.get("total_elapsed_ms"))
    if latency is not None:
        merged["latency_ms"] = latency

    models = workflow_result.get("llm_node_models")
    if isinstance(models, dict):
        for model in models.values():
            if isinstance(model, str) and model.strip() != "":
                merged["model"] = model
                break

    tokens: dict[str, int] = {}
    prompt = _as_non_negative_int(workflow_result.get("total_input_tokens"))
    completion = _as_non_negative_int(workflow_result.get("total_output_tokens"))
    total = _as_non_negative_int(workflow_result.get("total_tokens"))
    if prompt is not None:
        tokens["prompt"] = prompt
    if completion is not None:
        tokens["completion"] = completion
    if total is not None:
        tokens["total"] = total
    if tokens:
        merged["tokens"] = tokens

    if isinstance(telemetry_data, dict):
        merged.update(_sanitize_telemetry_data(telemetry_data))
    return _sanitize_telemetry_data(merged)


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
        auth_sessions_path: str = "/v1/auth/sessions",
        auth_refresh_path: str = "/v1/auth/sessions/refresh",
        csrf_header_name: str = "X-CSRF-Token",
        csrf_cookie_name: str = "sf_csrf_token",
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
        self._auth_sessions_path = (
            str(auth_sessions_path or "/v1/auth/sessions").strip()
            or "/v1/auth/sessions"
        )
        self._auth_refresh_path = (
            str(auth_refresh_path or "/v1/auth/sessions/refresh").strip()
            or "/v1/auth/sessions/refresh"
        )
        self._csrf_header_name = (
            str(csrf_header_name or "X-CSRF-Token").strip() or "X-CSRF-Token"
        )
        self._csrf_cookie_name = (
            str(csrf_cookie_name or "sf_csrf_token").strip() or "sf_csrf_token"
        )
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
        use_auth: bool = True,
    ) -> dict[str, Any]:
        client = self._get_client()
        auth_headers: dict[str, str] = {}
        auth_source = "none"
        if use_auth:
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
            and use_auth
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

    def _path(self, value: str) -> str:
        trimmed = str(value or "").strip()
        if trimmed == "":
            return "/"
        if trimmed.startswith("/"):
            return trimmed
        return f"/{trimmed}"

    def _csrf_token_from_cookie_jar(self) -> str:
        client = self._get_client()
        cookies = getattr(client, "cookies", None)
        if cookies is None:
            return ""
        for name in (self._csrf_cookie_name, "csrf_cookie"):
            try:
                value = cookies.get(name)
            except Exception:
                value = None
            if isinstance(value, str) and value.strip() != "":
                return value.strip()
        return ""

    async def create_auth_session(
        self,
        *,
        email: str,
        password: str,
        set_as_default_token: bool = True,
    ) -> AuthTokenResponse:
        email_value = str(email or "").strip()
        password_value = str(password or "")
        if email_value == "" or password_value == "":
            raise ValueError(
                "simpleflow sdk payload error: email and password are required"
            )
        response = await self._request(
            method="POST",
            path=self._path(self._auth_sessions_path),
            payload={"email": email_value, "password": password_value},
            use_auth=False,
        )
        access_token = str(response.get("access_token", "")).strip()
        if set_as_default_token and access_token != "":
            self._api_token = access_token
        return response  # type: ignore[return-value]

    async def refresh_auth_session(
        self,
        *,
        csrf_token: str | None = None,
        set_as_default_token: bool = True,
    ) -> AuthTokenResponse:
        header_token = (
            str(csrf_token or "").strip() or self._csrf_token_from_cookie_jar()
        )
        if header_token == "":
            raise ValueError(
                "simpleflow sdk auth error: csrf token is required; call create_auth_session first or pass csrf_token"
            )
        response = await self._request(
            method="POST",
            path=self._path(self._auth_refresh_path),
            extra_headers={self._csrf_header_name: header_token},
            use_auth=False,
        )
        access_token = str(response.get("access_token", "")).strip()
        if set_as_default_token and access_token != "":
            self._api_token = access_token
        return response  # type: ignore[return-value]

    async def validate_access_token(
        self,
        *,
        auth_token: str | None = None,
    ) -> PrincipalResponse:
        token = str(auth_token or "").strip() or self._api_token
        if token == "":
            raise ValueError("simpleflow sdk config error: auth_token is required")
        result = await self.fetch_current_user(auth_token=token)
        return result  # type: ignore[return-value]

    async def fetch_current_user(self, *, auth_token: str) -> PrincipalResponse:
        """Load the current user from ``GET /v1/me`` (org roles include ``member``, ``admin``, ``super_admin``)."""
        token = str(auth_token or "").strip()
        if token == "":
            raise ValueError("simpleflow sdk config error: auth_token is required")
        path = self._me_path if self._me_path.startswith("/") else f"/{self._me_path}"
        result = await self._get(path, auth_token=token)
        return result  # type: ignore[return-value]

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
        if not roles:
            role_single = str(me.get("role", "")).strip()
            if role_single != "":
                roles = [role_single]
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
        user_id: str | None = None,
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

    async def list_chat_sessions_page(
        self,
        *,
        agent_id: str,
        user_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        limit: int = 20,
        auth_token: str | None = None,
    ) -> ChatSessionsResponse:
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
        result: dict[str, Any] = {}
        sessions = response.get("sessions")
        if isinstance(sessions, list):
            result["sessions"] = [
                _normalize_chat_session(item)
                for item in sessions
                if isinstance(item, dict)
            ]
        page_value = response.get("page")
        if isinstance(page_value, int):
            result["page"] = page_value
        limit_value = response.get("limit")
        if isinstance(limit_value, int):
            result["limit"] = limit_value
        has_more = response.get("has_more")
        if isinstance(has_more, bool):
            result["has_more"] = has_more

        return result  # type: ignore[return-value]

    async def list_chat_sessions_typed(
        self,
        *,
        agent_id: str,
        user_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        limit: int = 20,
        auth_token: str | None = None,
    ) -> list[ChatSession]:
        response = await self.list_chat_sessions_page(
            agent_id=agent_id,
            user_id=user_id,
            status=status,
            page=page,
            limit=limit,
            auth_token=auth_token,
        )
        sessions = response.get("sessions")
        if not isinstance(sessions, list):
            return []
        return sessions

    async def list_chat_messages(
        self,
        *,
        agent_id: str,
        chat_id: str,
        user_id: str | None = None,
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
        unknown_keys = sorted(
            [key for key in body.keys() if key not in ALLOWED_CHAT_MESSAGE_KEYS]
        )
        if unknown_keys:
            raise ValueError(
                "simpleflow sdk payload error: unknown keys in chat message payload: "
                + ", ".join(unknown_keys)
            )
        required_keys = ["agent_id", "user_id", "chat_id", "message_id", "role"]
        missing = [key for key in required_keys if str(body.get(key, "")).strip() == ""]
        if missing:
            raise ValueError(
                f"simpleflow sdk payload error: missing required keys: {', '.join(missing)}"
            )

        role = str(body.get("role", "")).strip().lower()
        if role not in VALID_CHAT_ROLES:
            raise ValueError(
                "simpleflow sdk payload error: role must be one of: system, user, assistant, tool"
            )
        body["role"] = role

        if body.get("output_data") is not None and role != "assistant":
            raise ValueError(
                "simpleflow sdk payload error: output_data is only allowed when role is assistant"
            )

        body["content"] = _sanitize_content(body.get("content"))
        body["telemetry_data"] = _sanitize_telemetry_data(body.get("telemetry_data"))

        output_data = body.get("output_data")
        if output_data is not None:
            body["output_data"] = _sanitize_message_output_data(output_data)

        headers: dict[str, str] = {}
        if idempotency_key != "":
            headers["Idempotency-Key"] = idempotency_key
        return await self._post(
            self._chat_sessions_path,
            body,
            auth_token=auth_token,
            extra_headers=headers,
        )

    def build_chat_message_from_simple_agents_result(
        self,
        *,
        agent_id: str,
        user_id: str,
        chat_id: str,
        message_id: str,
        workflow_result: Any,
        telemetry_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = _normalize_payload(workflow_result)
        output_data = _sanitize_message_output_data(payload)
        return {
            "agent_id": str(agent_id or "").strip(),
            "user_id": str(user_id or "").strip(),
            "chat_id": str(chat_id or "").strip(),
            "message_id": str(message_id or "").strip(),
            "role": "assistant",
            "content": {"text": _stringify_content(payload.get("terminal_output"))},
            "telemetry_data": _build_telemetry_data_from_workflow_result(
                payload, telemetry_data
            ),
            "output_data": output_data,
        }

    async def write_chat_message_from_simple_agents_result(
        self,
        *,
        agent_id: str,
        user_id: str,
        chat_id: str,
        message_id: str,
        workflow_result: Any,
        telemetry_data: dict[str, Any] | None = None,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        message = self.build_chat_message_from_simple_agents_result(
            agent_id=agent_id,
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            workflow_result=workflow_result,
            telemetry_data=telemetry_data,
        )
        return await self.write_chat_message(message, auth_token=auth_token)

    async def get_chat_message_output(
        self,
        *,
        message_id: str,
        agent_id: str,
        chat_id: str,
        user_id: str | None = None,
        auth_token: str | None = None,
    ) -> MessageOutputResponse:
        mid = str(message_id or "").strip()
        if mid == "":
            raise ValueError("simpleflow sdk config error: message_id is required")
        path = self._path_with_query(
            f"/v1/chat/messages/{quote(mid, safe='')}/output",
            {
                "agent_id": agent_id,
                "chat_id": chat_id,
                "user_id": user_id,
            },
        )
        result = await self._get(path, auth_token=auth_token)
        return result  # type: ignore[return-value]

    async def upsert_chat_message_output(
        self,
        *,
        message_id: str,
        agent_id: str,
        chat_id: str,
        user_id: str,
        output_data: Any,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        mid = str(message_id or "").strip()
        if mid == "":
            raise ValueError("simpleflow sdk config error: message_id is required")
        uid = str(user_id or "").strip()
        if uid == "":
            raise ValueError("simpleflow sdk payload error: user_id is required")
        payload = {
            "agent_id": str(agent_id or "").strip(),
            "chat_id": str(chat_id or "").strip(),
            "user_id": uid,
            "output_data": _sanitize_message_output_data(output_data),
        }
        return await self._post(
            f"/v1/chat/messages/{quote(mid, safe='')}/output",
            payload,
            auth_token=auth_token,
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
        base_telemetry = _build_telemetry_data_from_workflow_result(
            payload, telemetry_data
        )
        role_value = str(role or "").strip().lower()
        if role_value not in VALID_CHAT_ROLES:
            raise ValueError(
                "simpleflow sdk payload error: role must be one of: system, user, assistant, tool"
            )

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
                message_telemetry = _sanitize_telemetry_data(
                    {
                        **base_telemetry,
                        "event_type": "assistant.step_output",
                        "tags": [f"node:{node_id}"],
                    }
                )
                messages.append(
                    {
                        "agent_id": agent_id,
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "message_id": (
                            f"{message_id_prefix}_{counter}_{_safe_message_id_suffix(node_id)}"
                        ),
                        "role": role_value,
                        "content": {"text": _stringify_content(node_output)},
                        "telemetry_data": message_telemetry,
                    }
                )
                counter += 1

        if include_terminal_output and payload.get("terminal_output") is not None:
            message_telemetry = _sanitize_telemetry_data(
                {
                    **base_telemetry,
                    "event_type": "assistant.reply",
                    "tags": [f"terminal:{terminal_node}"] if terminal_node else [],
                }
            )
            messages.append(
                {
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "message_id": (
                        f"{message_id_prefix}_{counter}_{_safe_message_id_suffix(terminal_node or 'final')}"
                    ),
                    "role": role_value,
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

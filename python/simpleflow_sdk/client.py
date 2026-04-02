from __future__ import annotations

from dataclasses import fields, is_dataclass
from hashlib import sha256
from math import isfinite
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx

if TYPE_CHECKING:
    from .response_models import ChatSession, InvokeResult, RuntimeActivationResult


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


class SimpleFlowLifecycleError(SimpleFlowRequestError):
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


def _dataclass_to_payload(payload: Any) -> dict[str, Any]:
    if not is_dataclass(payload):
        raise TypeError(
            "simpleflow sdk payload error: payload must be a dataclass, dict, or None"
        )
    return {field.name: getattr(payload, field.name) for field in fields(payload)}


def _registration_identifier(registration: dict[str, Any]) -> str:
    return str(registration.get("id", registration.get("registration_id", ""))).strip()


def _resolve_workflow_event_context(
    normalized_result: dict[str, Any],
    *,
    organization_id: str,
    user_id: str,
) -> dict[str, Any]:
    metadata = normalized_result.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    telemetry = metadata_dict.get("telemetry")
    telemetry_dict = telemetry if isinstance(telemetry, dict) else {}
    trace = metadata_dict.get("trace")
    trace_dict = trace if isinstance(trace, dict) else {}
    tenant = trace_dict.get("tenant")
    tenant_dict = tenant if isinstance(tenant, dict) else {}

    conversation_id = str(tenant_dict.get("conversation_id", "")).strip()
    if conversation_id == "":
        conversation_id = str(trace_dict.get("conversation_id", "")).strip()

    request_id = str(tenant_dict.get("request_id", "")).strip()
    if request_id == "":
        request_id = str(trace_dict.get("request_id", "")).strip()

    run_id = str(tenant_dict.get("run_id", "")).strip()
    if run_id == "":
        run_id = str(normalized_result.get("run_id", "")).strip()

    resolved_organization_id = (
        organization_id.strip()
        or str(tenant_dict.get("organization_id", "")).strip()
        or str(trace_dict.get("organization_id", "")).strip()
        or str(normalized_result.get("organization_id", "")).strip()
    )
    resolved_user_id = (
        user_id.strip()
        or str(tenant_dict.get("user_id", "")).strip()
        or str(trace_dict.get("user_id", "")).strip()
        or str(normalized_result.get("user_id", "")).strip()
    )
    trace_id = str(telemetry_dict.get("trace_id", "")).strip()
    sampled_value = telemetry_dict.get("sampled")
    sampled = sampled_value if isinstance(sampled_value, bool) else None

    return {
        "conversation_id": conversation_id,
        "request_id": request_id,
        "run_id": run_id,
        "organization_id": resolved_organization_id,
        "user_id": resolved_user_id,
        "trace_id": trace_id,
        "sampled": sampled,
    }


def _normalize_runtime_activation_result(
    value: dict[str, Any],
) -> RuntimeActivationResult:
    registration = value.get("registration")
    normalized_registration: dict[str, Any]
    if isinstance(registration, dict):
        normalized_registration = registration
    else:
        normalized_registration = {}

    result: RuntimeActivationResult = {
        "status": "active",
        "registration": normalized_registration,
        "registration_id": str(value.get("registration_id", "")).strip(),
        "created": bool(value.get("created", False)),
        "validated": bool(value.get("validated", False)),
        "activated": bool(value.get("activated", False)),
    }
    validation = value.get("validation")
    if isinstance(validation, dict):
        result["validation"] = validation
    return result


def _normalize_invoke_result(value: dict[str, Any]) -> InvokeResult:
    result: InvokeResult = {}
    if isinstance(value.get("schema_version"), str):
        result["schema_version"] = str(value["schema_version"])
    if isinstance(value.get("run_id"), str):
        result["run_id"] = str(value["run_id"])
    if isinstance(value.get("status"), str):
        result["status"] = str(value["status"])
    if isinstance(value.get("output"), dict):
        result["output"] = value["output"]
    if isinstance(value.get("error"), dict):
        result["error"] = value["error"]
    if isinstance(value.get("metrics"), dict):
        result["metrics"] = value["metrics"]
    return result


def _normalize_chat_session(value: dict[str, Any]) -> ChatSession:
    session: ChatSession = {}
    if isinstance(value.get("chat_id"), str):
        session["chat_id"] = str(value["chat_id"])
    if isinstance(value.get("status"), str):
        session["status"] = str(value["status"])
    if isinstance(value.get("agent_id"), str):
        session["agent_id"] = str(value["agent_id"])
    if isinstance(value.get("user_id"), str):
        session["user_id"] = str(value["user_id"])
    if isinstance(value.get("metadata"), dict):
        session["metadata"] = value["metadata"]
    return session


def _normalize_payload(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if is_dataclass(payload):
        return _dataclass_to_payload(payload)
    if isinstance(payload, dict):
        return payload
    raise TypeError(
        "simpleflow sdk payload error: payload must be a dataclass, dict, or None"
    )


def _validate_sample_rate(sample_rate: float | None) -> None:
    if sample_rate is None:
        return
    if not isfinite(sample_rate) or sample_rate < 0.0 or sample_rate > 1.0:
        raise ValueError(
            "simpleflow sdk config error: telemetry sample_rate must be a finite value between 0.0 and 1.0"
        )


def _count_workflow_events_by_type(workflow_result: dict[str, Any]) -> dict[str, int]:
    events = workflow_result.get("events")
    if not isinstance(events, list):
        return {}

    counts: dict[str, int] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("event_type", "")).strip()
        if event_type == "":
            continue
        counts[event_type] = counts.get(event_type, 0) + 1
    return counts


def _extract_workflow_nerdstats(
    workflow_result: dict[str, Any],
) -> dict[str, Any] | None:
    direct_top_level = workflow_result.get("nerdstats")
    if isinstance(direct_top_level, dict):
        return direct_top_level

    metadata = workflow_result.get("metadata")
    if isinstance(metadata, dict):
        direct_metadata = metadata.get("nerdstats")
        if isinstance(direct_metadata, dict):
            return direct_metadata

    events = workflow_result.get("events")
    if not isinstance(events, list):
        return None

    for event in reversed(events):
        if not isinstance(event, dict):
            continue
        if str(event.get("event_type", "")).strip() != "workflow_completed":
            continue
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            continue
        nerdstats = metadata.get("nerdstats")
        if isinstance(nerdstats, dict):
            return nerdstats
    return None


def _extract_model_usage(nerdstats: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(nerdstats, dict):
        return []

    totals_by_model: dict[str, dict[str, float]] = {}
    step_details = nerdstats.get("step_details")
    if isinstance(step_details, list):
        for step in step_details:
            if not isinstance(step, dict):
                continue
            model_name = str(step.get("model_name", "")).strip()
            if model_name == "":
                continue
            bucket = totals_by_model.setdefault(
                model_name,
                {
                    "request_count": 0.0,
                    "prompt_tokens": 0.0,
                    "completion_tokens": 0.0,
                    "total_tokens": 0.0,
                    "reasoning_tokens": 0.0,
                    "elapsed_ms": 0.0,
                },
            )
            bucket["request_count"] += 1.0
            bucket["prompt_tokens"] += float(step.get("prompt_tokens", 0) or 0)
            bucket["completion_tokens"] += float(step.get("completion_tokens", 0) or 0)
            bucket["total_tokens"] += float(step.get("total_tokens", 0) or 0)
            bucket["reasoning_tokens"] += float(step.get("reasoning_tokens", 0) or 0)
            bucket["elapsed_ms"] += float(step.get("elapsed_ms", 0) or 0)

    llm_node_models = nerdstats.get("llm_node_models")
    if isinstance(llm_node_models, dict):
        for _, raw_model in llm_node_models.items():
            model_name = str(raw_model).strip()
            if model_name == "":
                continue
            totals_by_model.setdefault(
                model_name,
                {
                    "request_count": 0.0,
                    "prompt_tokens": 0.0,
                    "completion_tokens": 0.0,
                    "total_tokens": 0.0,
                    "reasoning_tokens": 0.0,
                    "elapsed_ms": 0.0,
                },
            )

    model_usage: list[dict[str, Any]] = []
    for model_name in sorted(totals_by_model.keys()):
        bucket = totals_by_model[model_name]
        model_usage.append(
            {
                "model": model_name,
                "request_count": int(bucket["request_count"]),
                "prompt_tokens": int(bucket["prompt_tokens"]),
                "completion_tokens": int(bucket["completion_tokens"]),
                "total_tokens": int(bucket["total_tokens"]),
                "reasoning_tokens": int(bucket["reasoning_tokens"]),
                "elapsed_ms": int(bucket["elapsed_ms"]),
            }
        )
    return model_usage


def _extract_tool_usage(event_counts: dict[str, int]) -> list[dict[str, Any]]:
    started = int(event_counts.get("node_tool_start", 0))
    completed = int(event_counts.get("node_tool_completed", 0))
    errors = int(event_counts.get("node_tool_error", 0))
    if started == 0 and completed == 0 and errors == 0:
        return []
    return [
        {
            "tool": "workflow_tools",
            "started_count": started,
            "completed_count": completed,
            "error_count": errors,
        }
    ]


def _build_usage_summary(nerdstats: dict[str, Any] | None) -> dict[str, Any]:
    def _as_number_or_none(value: Any) -> int | float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        return None

    def _first_number_or_none(*values: Any) -> int | float | None:
        for value in values:
            converted = _as_number_or_none(value)
            if converted is not None:
                return converted
        return None

    def _as_string_or_none(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    if not isinstance(nerdstats, dict):
        return {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "reasoning_tokens": None,
            "ttft_ms": None,
            "total_elapsed_ms": None,
            "tokens_per_second": None,
            "token_metrics_available": False,
            "token_metrics_source": None,
            "llm_nodes_without_usage": [],
        }

    token_metrics_available = nerdstats.get("token_metrics_available")
    if not isinstance(token_metrics_available, bool):
        token_metrics_available = True

    raw_nodes_without_usage = nerdstats.get("llm_nodes_without_usage")
    llm_nodes_without_usage: list[str] = []
    if isinstance(raw_nodes_without_usage, list):
        for node_id in raw_nodes_without_usage:
            text = str(node_id or "").strip()
            if text != "":
                llm_nodes_without_usage.append(text)

    return {
        "prompt_tokens": (
            _first_number_or_none(
                nerdstats.get("total_input_tokens"), nerdstats.get("prompt_tokens")
            )
            if token_metrics_available
            else None
        ),
        "completion_tokens": (
            _first_number_or_none(
                nerdstats.get("total_output_tokens"), nerdstats.get("completion_tokens")
            )
            if token_metrics_available
            else None
        ),
        "total_tokens": (
            _as_number_or_none(nerdstats.get("total_tokens"))
            if token_metrics_available
            else None
        ),
        "reasoning_tokens": (
            _first_number_or_none(
                nerdstats.get("total_reasoning_tokens"),
                nerdstats.get("reasoning_tokens"),
            )
            if token_metrics_available
            else None
        ),
        "ttft_ms": _as_number_or_none(nerdstats.get("ttft_ms")),
        "total_elapsed_ms": _as_number_or_none(nerdstats.get("total_elapsed_ms")),
        "tokens_per_second": _as_number_or_none(nerdstats.get("tokens_per_second")),
        "token_metrics_available": token_metrics_available,
        "token_metrics_source": _as_string_or_none(
            nerdstats.get("token_metrics_source")
        ),
        "llm_nodes_without_usage": llm_nodes_without_usage,
    }


def _build_canonical_telemetry_envelope(
    *,
    workflow_result: dict[str, Any],
    agent_id: str,
    organization_id: str,
    user_id: str,
    run_id: str,
    trace_id: str,
    conversation_id: str,
    request_id: str,
    sampled: bool,
    include_raw: bool,
) -> dict[str, Any]:
    metadata = workflow_result.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    trace_meta = metadata_dict.get("trace")
    trace_dict = trace_meta if isinstance(trace_meta, dict) else {}

    event_counts = _count_workflow_events_by_type(workflow_result)
    nerdstats = _extract_workflow_nerdstats(workflow_result)
    usage = _build_usage_summary(nerdstats)
    model_usage = _extract_model_usage(nerdstats)
    tool_usage = _extract_tool_usage(event_counts)

    payload: dict[str, Any] = {
        "schema_version": "telemetry-envelope.v1",
        "identity": {
            "organization_id": organization_id,
            "agent_id": agent_id,
            "user_id": user_id,
        },
        "trace": {
            "trace_id": trace_id,
            "span_id": str(trace_dict.get("span_id", "")).strip(),
            "tenant_id": str(trace_dict.get("tenant_id", "")).strip(),
            "conversation_id": conversation_id,
            "request_id": request_id,
            "run_id": run_id,
            "sampled": sampled,
        },
        "workflow": {
            "workflow_id": str(workflow_result.get("workflow_id", "")).strip(),
            "terminal_node": str(workflow_result.get("terminal_node", "")).strip(),
            "status": str(workflow_result.get("status", "")).strip() or "completed",
            "total_elapsed_ms": int(workflow_result.get("total_elapsed_ms", 0) or 0),
            "ttft_ms": usage.get("ttft_ms"),
        },
        "usage": usage,
        "model_usage": model_usage,
        "tool_usage": tool_usage,
        "event_counts": event_counts,
    }

    if isinstance(nerdstats, dict):
        payload["nerdstats"] = nerdstats
    if include_raw:
        payload["raw"] = workflow_result
    return payload


def _build_trace_url(
    trace_id: str, trace_ui_base_url: str = "http://localhost:16686"
) -> str:
    normalized_trace_id = trace_id.strip()
    if normalized_trace_id == "":
        return ""
    normalized_base_url = trace_ui_base_url.strip().rstrip("/")
    if normalized_base_url == "":
        normalized_base_url = "http://localhost:16686"
    return f"{normalized_base_url}/trace/{normalized_trace_id}"


def _should_sample(trace_id: str, sample_rate: float | None) -> bool:
    if sample_rate is None:
        return True
    if sample_rate <= 0.0:
        return False
    if sample_rate >= 1.0:
        return True
    digest = sha256(trace_id.encode("utf-8")).digest()
    value = int.from_bytes(digest[0:8], byteorder="big", signed=False)
    ratio = value / ((1 << 64) - 1)
    return ratio <= sample_rate


class SimpleFlowClient:
    def __init__(
        self,
        base_url: str,
        api_token: str | None = None,
        oauth_client_id: str | None = None,
        oauth_client_secret: str | None = None,
        oauth_token_path: str = "/v1/oauth/token",
        oauth_token_leeway_seconds: int = 30,
        auth_sessions_path: str = "/v1/auth/sessions",
        auth_current_session_path: str = "/v1/auth/sessions/current",
        auth_me_path: str = "/v1/me",
        runtime_register_path: str = "/v1/runtime/registrations",
        runtime_invoke_path: str = "/v1/runtime/invoke",
        runtime_events_path: str = "/v1/runtime/events",
        runtime_activate_path: str = "/v1/runtime/registrations/{registration_id}/activate",
        runtime_deactivate_path: str = "/v1/runtime/registrations/{registration_id}/deactivate",
        runtime_validate_path: str = "/v1/runtime/registrations/{registration_id}/validate",
        chat_messages_path: str = "/v1/runtime/chat/messages",
        queue_contracts_path: str = "/v1/runtime/queue/contracts",
        chat_sessions_path: str = "/v1/chat/history/sessions",
        chat_history_path: str = "/v1/chat/history/messages",
        timeout_seconds: float = 10.0,
    ) -> None:
        if base_url.strip() == "":
            raise ValueError("simpleflow sdk config error: base_url is required")
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token.strip() if api_token is not None else ""
        self._oauth_client_id = (
            oauth_client_id.strip() if oauth_client_id is not None else ""
        )
        self._oauth_client_secret = (
            oauth_client_secret.strip() if oauth_client_secret is not None else ""
        )
        self._oauth_token_path = oauth_token_path
        self._oauth_token_leeway_seconds = max(0, int(oauth_token_leeway_seconds))
        self._oauth_access_token = ""
        self._oauth_access_token_expires_at_unix = 0.0
        self._auth_sessions_path = auth_sessions_path
        self._auth_current_session_path = auth_current_session_path
        self._auth_me_path = auth_me_path
        self._runtime_register_path = runtime_register_path
        self._runtime_invoke_path = runtime_invoke_path
        self._runtime_events_path = runtime_events_path
        self._runtime_activate_path = runtime_activate_path
        self._runtime_deactivate_path = runtime_deactivate_path
        self._runtime_validate_path = runtime_validate_path
        self._chat_messages_path = chat_messages_path
        self._queue_contracts_path = queue_contracts_path
        self._chat_sessions_path = chat_sessions_path
        self._chat_history_path = chat_history_path
        self._client = httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def create_session(self, email: str, password: str) -> dict[str, Any]:
        payload = {"email": email, "password": password}
        return self._post(self._auth_sessions_path, payload, auth_token="")

    def delete_current_session(self, auth_token: str | None = None) -> None:
        self._delete(self._auth_current_session_path, auth_token=auth_token)

    def get_me(self, auth_token: str | None = None) -> dict[str, Any]:
        return self._get(self._auth_me_path, auth_token=auth_token)

    def register_runtime(
        self, registration: Any, auth_token: str | None = None
    ) -> dict[str, Any]:
        return self._post(
            self._runtime_register_path, registration, auth_token=auth_token
        )

    def list_runtime_registrations(
        self,
        *,
        agent_id: str,
        agent_version: str,
        auth_token: str | None = None,
    ) -> list[dict[str, Any]]:
        path = self._path_with_query(
            self._runtime_register_path,
            {
                "agent_id": agent_id,
                "agent_version": agent_version,
            },
        )
        response = self._get(path, auth_token=auth_token)
        registrations = response.get("registrations")
        if isinstance(registrations, list):
            return [item for item in registrations if isinstance(item, dict)]
        return []

    def activate_runtime_registration(
        self, registration_id: str, auth_token: str | None = None
    ) -> None:
        self._post(
            self._runtime_registration_action_path(
                self._runtime_activate_path, registration_id
            ),
            {},
            auth_token=auth_token,
        )

    def deactivate_runtime_registration(
        self, registration_id: str, auth_token: str | None = None
    ) -> None:
        self._post(
            self._runtime_registration_action_path(
                self._runtime_deactivate_path, registration_id
            ),
            {},
            auth_token=auth_token,
        )

    def validate_runtime_registration(
        self, registration_id: str, auth_token: str | None = None
    ) -> dict[str, Any]:
        return self._post(
            self._runtime_registration_action_path(
                self._runtime_validate_path, registration_id
            ),
            {},
            auth_token=auth_token,
        )

    def ensure_runtime_registration_active(
        self,
        *,
        registration: Any,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        return dict(
            self.ensure_runtime_registration_active_typed(
                registration=registration,
                auth_token=auth_token,
            )
        )

    def ensure_runtime_registration_active_typed(
        self,
        *,
        registration: Any,
        auth_token: str | None = None,
    ) -> RuntimeActivationResult:
        payload = _normalize_payload(registration)
        requested_agent_id = str(payload.get("agent_id", "")).strip()
        requested_agent_version = str(payload.get("agent_version", "")).strip()
        if requested_agent_id == "" or requested_agent_version == "":
            raise ValueError(
                "simpleflow sdk payload error: registration agent_id and agent_version are required"
            )

        existing = self.list_runtime_registrations(
            agent_id=requested_agent_id,
            agent_version=requested_agent_version,
            auth_token=auth_token,
        )
        active = self._active_runtime_registration_result(existing)
        if active is not None:
            return _normalize_runtime_activation_result(active)

        target, created = self._resolve_registration_target(
            existing=existing,
            payload=payload,
            auth_token=auth_token,
        )
        registration_id = self._registration_id_or_raise(target)

        validation = self.validate_runtime_registration(
            registration_id, auth_token=auth_token
        )
        self.activate_runtime_registration(registration_id, auth_token=auth_token)
        return _normalize_runtime_activation_result(
            {
                "status": "active",
                "registration": target,
                "registration_id": registration_id,
                "validation": validation,
                "created": created,
                "validated": True,
                "activated": True,
            }
        )

    def _active_runtime_registration_result(
        self, registrations: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        for item in registrations:
            status = str(item.get("status", "")).strip().lower()
            if status == "active":
                return {
                    "status": "active",
                    "registration": item,
                    "registration_id": _registration_identifier(item),
                    "created": False,
                    "validated": False,
                    "activated": False,
                }
        return None

    def _resolve_registration_target(
        self,
        *,
        existing: list[dict[str, Any]],
        payload: dict[str, Any],
        auth_token: str | None,
    ) -> tuple[dict[str, Any], bool]:
        if len(existing) > 0:
            return existing[0], False
        return self.register_runtime(payload, auth_token=auth_token), True

    def _registration_id_or_raise(self, registration: dict[str, Any]) -> str:
        registration_id = _registration_identifier(registration)
        if registration_id != "":
            return registration_id
        raise SimpleFlowLifecycleError(
            status_code=502,
            detail="registration response did not include registration id",
            path=self._runtime_register_path,
        )

    def invoke(self, request: Any, auth_token: str | None = None) -> dict[str, Any]:
        return dict(self.invoke_typed(request, auth_token=auth_token))

    def invoke_typed(self, request: Any, auth_token: str | None = None) -> InvokeResult:
        response = self._post(self._runtime_invoke_path, request, auth_token=auth_token)
        return _normalize_invoke_result(response)

    def write_event(self, event: Any) -> None:
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
        self._post(self._runtime_events_path, body, extra_headers=headers)

    def report_runtime_event(self, event: Any) -> None:
        self.write_event(event)

    def write_chat_message(self, message: Any) -> None:
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
        self._post(self._chat_messages_path, body, extra_headers=headers)

    def publish_queue_contract(self, contract: Any) -> None:
        body = _normalize_payload(contract)
        if str(body.get("contract_name", "")).strip() == "":
            body["contract_name"] = (
                str(body.get("message_id", "")).strip() or "runtime.queue.contract"
            )
        if str(body.get("contract_version", "")).strip() == "":
            body["contract_version"] = "v1"
        if str(body.get("status", "")).strip() == "":
            body["status"] = "draft"
        if body.get("schema") is None:
            body["schema"] = body.get("payload") or {}
        if body.get("transport") is None:
            body["transport"] = {}
        idempotency_key = str(body.pop("idempotency_key", "")).strip()
        headers: dict[str, str] = {}
        if idempotency_key != "":
            headers["Idempotency-Key"] = idempotency_key
        self._post(self._queue_contracts_path, body, extra_headers=headers)

    def list_chat_history_messages(
        self,
        *,
        agent_id: str,
        chat_id: str,
        user_id: str,
        limit: int = 50,
        auth_token: str | None = None,
    ) -> list[dict[str, Any]]:
        path = self._path_with_query(
            self._chat_history_path,
            {
                "agent_id": agent_id,
                "chat_id": chat_id,
                "user_id": user_id,
                "limit": limit,
            },
        )
        response = self._get(path, auth_token=auth_token)
        messages = response.get("messages")
        if isinstance(messages, list):
            return [item for item in messages if isinstance(item, dict)]
        return []

    def list_chat_sessions(
        self,
        *,
        agent_id: str,
        user_id: str,
        status: str = "active",
        limit: int = 50,
        auth_token: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            dict(session)
            for session in self.list_chat_sessions_typed(
                agent_id=agent_id,
                user_id=user_id,
                status=status,
                limit=limit,
                auth_token=auth_token,
            )
        ]

    def list_chat_sessions_typed(
        self,
        *,
        agent_id: str,
        user_id: str,
        status: str = "active",
        limit: int = 50,
        auth_token: str | None = None,
    ) -> list[ChatSession]:
        path = self._path_with_query(
            self._chat_sessions_path,
            {
                "agent_id": agent_id,
                "user_id": user_id,
                "status": status,
                "limit": limit,
            },
        )
        response = self._get(path, auth_token=auth_token)
        sessions = response.get("sessions")
        if not isinstance(sessions, list):
            return []
        return [
            _normalize_chat_session(item) for item in sessions if isinstance(item, dict)
        ]

    def create_chat_history_message(
        self, message: Any, auth_token: str | None = None
    ) -> dict[str, Any]:
        return self._post(self._chat_history_path, message, auth_token=auth_token)

    def update_chat_history_message(
        self,
        *,
        message_id: str,
        agent_id: str,
        chat_id: str,
        user_id: str,
        content: Any,
        metadata: Any,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "content": _normalize_payload(content),
            "metadata": _normalize_payload(metadata),
        }
        return self._patch(
            f"{self._chat_history_path}/{message_id}",
            payload,
            auth_token=auth_token,
        )

    def write_event_from_workflow_result(
        self,
        *,
        agent_id: str,
        workflow_result: Any,
        event_type: str = "runtime.workflow.completed",
        organization_id: str = "",
        user_id: str = "",
        include_raw: bool = False,
    ) -> None:
        normalized_result = _normalize_payload(workflow_result)
        context = _resolve_workflow_event_context(
            normalized_result,
            organization_id=organization_id,
            user_id=user_id,
        )
        canonical_payload = _build_canonical_telemetry_envelope(
            workflow_result=normalized_result,
            agent_id=agent_id,
            organization_id=str(context["organization_id"]),
            user_id=str(context["user_id"]),
            run_id=str(context["run_id"]),
            trace_id=str(context["trace_id"]),
            conversation_id=str(context["conversation_id"]),
            request_id=str(context["request_id"]),
            sampled=(
                context["sampled"] if isinstance(context["sampled"], bool) else True
            ),
            include_raw=include_raw,
        )

        self.write_event(
            {
                "event_type": event_type,
                "agent_id": agent_id,
                "organization_id": context["organization_id"],
                "user_id": context["user_id"],
                "run_id": context["run_id"],
                "conversation_id": context["conversation_id"],
                "request_id": context["request_id"],
                "trace_id": context["trace_id"],
                "sampled": context["sampled"],
                "payload": canonical_payload,
            }
        )

    def write_chat_message_from_workflow_result(
        self,
        *,
        agent_id: str,
        organization_id: str,
        run_id: str,
        role: str,
        workflow_result: Any,
        trace_id: str = "",
        span_id: str = "",
        tenant_id: str = "",
        trace_ui_base_url: str = "http://localhost:16686",
        chat_id: str | None = None,
        message_id: str | None = None,
        direction: str | None = None,
        created_at_ms: int | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        normalized_result = _normalize_payload(workflow_result)
        normalized_trace_id = trace_id.strip()
        events = normalized_result.get("events")
        event_counts = _count_workflow_events_by_type(normalized_result)
        nerdstats = _extract_workflow_nerdstats(normalized_result)

        content = {
            "reply": normalized_result.get("terminal_output"),
            "terminal_output": normalized_result.get("terminal_output"),
            "workflow": {
                "workflow_id": normalized_result.get("workflow_id"),
                "terminal_node": normalized_result.get("terminal_node"),
            },
        }

        metadata: dict[str, Any] = {
            "source": "runtime.workflow.invoke",
            "workflow_id": normalized_result.get("workflow_id"),
            "terminal_node": normalized_result.get("terminal_node"),
            "trace": normalized_result.get("trace", []),
            "step_timings": normalized_result.get("step_timings", []),
            "event_counts": event_counts,
            "nerdstats": nerdstats,
            "llm_node_metrics": normalized_result.get("llm_node_metrics", {}),
            "total_elapsed_ms": normalized_result.get("total_elapsed_ms"),
            "trace_context": {
                "trace_id": normalized_trace_id,
                "span_id": span_id.strip(),
                "tenant_id": tenant_id.strip(),
                "trace_url": _build_trace_url(
                    normalized_trace_id, trace_ui_base_url=trace_ui_base_url
                ),
            },
        }
        if isinstance(events, list):
            metadata["events"] = events

        self.write_chat_message(
            {
                "agent_id": agent_id,
                "organization_id": organization_id,
                "run_id": run_id,
                "role": role,
                "chat_id": chat_id,
                "message_id": message_id,
                "direction": direction,
                "content": content,
                "metadata": metadata,
                "idempotency_key": idempotency_key,
                "created_at_ms": created_at_ms,
            }
        )

    def with_telemetry(
        self,
        *,
        mode: str = "simpleflow",
        sample_rate: float | None = None,
        otlp_sink: Any | None = None,
        default_trace: dict[str, str] | None = None,
    ) -> TelemetryBridge:
        return TelemetryBridge(
            client=self,
            mode=mode,
            sample_rate=sample_rate,
            otlp_sink=otlp_sink,
            default_trace=default_trace,
        )

    def _post(
        self,
        path: str,
        payload: Any,
        extra_headers: dict[str, str] | None = None,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        body = _normalize_payload(payload)
        return self._request_json(
            method="POST",
            path=path,
            payload=body,
            extra_headers=extra_headers,
            auth_token=auth_token,
            include_json_content_type=True,
            wrap_json_decode_error=True,
        )

    def _get(self, path: str, auth_token: str | None = None) -> dict[str, Any]:
        return self._request_json(method="GET", path=path, auth_token=auth_token)

    def _patch(
        self, path: str, payload: Any, auth_token: str | None = None
    ) -> dict[str, Any]:
        body = _normalize_payload(payload)
        return self._request_json(
            method="PATCH",
            path=path,
            payload=body,
            auth_token=auth_token,
            include_json_content_type=True,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        *,
        extra_headers: dict[str, str] | None = None,
        auth_token: str | None = None,
        include_json_content_type: bool = False,
        wrap_json_decode_error: bool = False,
    ) -> dict[str, Any]:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self._base_url}{normalized_path}"

        headers = self._authorization_headers(auth_token)
        if include_json_content_type:
            headers = {"Content-Type": "application/json", **headers}
        if extra_headers is not None:
            headers.update(extra_headers)

        upper_method = method.upper()
        if upper_method == "GET":
            response = self._client.get(url, headers=headers)
        elif upper_method == "POST":
            response = self._client.post(url, json=payload, headers=headers)
        elif upper_method == "PATCH":
            response = self._client.patch(url, json=payload, headers=headers)
        else:
            raise ValueError(
                f"simpleflow sdk request error: unsupported method {method}"
            )

        if response.status_code < 200 or response.status_code >= 300:
            self._raise_request_error(
                path=normalized_path,
                status_code=response.status_code,
                body=response.text,
            )
        if response.text.strip() == "":
            return {}
        try:
            decoded = response.json()
        except ValueError as exc:
            if wrap_json_decode_error:
                raise RuntimeError(
                    "simpleflow sdk request error: expected JSON response body"
                ) from exc
            raise
        if isinstance(decoded, dict):
            return decoded
        raise RuntimeError(
            "simpleflow sdk request error: expected JSON object response body"
        )

    def _delete(self, path: str, auth_token: str | None = None) -> None:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self._base_url}{normalized_path}"
        headers = self._authorization_headers(auth_token)
        response = self._client.delete(url, headers=headers)
        if response.status_code < 200 or response.status_code >= 300:
            self._raise_request_error(
                path=normalized_path,
                status_code=response.status_code,
                body=response.text,
            )

    def _authorization_headers(self, auth_token: str | None = None) -> dict[str, str]:
        token = ""
        if auth_token is None:
            token = self._api_token
            if (
                token == ""
                and self._oauth_client_id != ""
                and self._oauth_client_secret != ""
            ):
                token = self._ensure_oauth_access_token()
        else:
            token = auth_token.strip()
        if token == "":
            return {}
        return {"Authorization": f"Bearer {token}"}

    def _ensure_oauth_access_token(self) -> str:
        now = time.time()
        if (
            self._oauth_access_token != ""
            and now + float(self._oauth_token_leeway_seconds)
            < self._oauth_access_token_expires_at_unix
        ):
            return self._oauth_access_token

        normalized_path = (
            self._oauth_token_path
            if self._oauth_token_path.startswith("/")
            else f"/{self._oauth_token_path}"
        )
        url = f"{self._base_url}{normalized_path}"
        response = self._client.post(
            url,
            json={
                "grant_type": "client_credentials",
                "client_id": self._oauth_client_id,
                "client_secret": self._oauth_client_secret,
            },
            headers={"Content-Type": "application/json"},
        )
        if response.status_code < 200 or response.status_code >= 300:
            self._raise_request_error(
                path=normalized_path,
                status_code=response.status_code,
                body=response.text,
            )

        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(
                "simpleflow sdk oauth error: expected JSON object token response"
            )
        access_token = str(payload.get("access_token", "")).strip()
        if access_token == "":
            raise RuntimeError(
                "simpleflow sdk oauth error: token response missing access_token"
            )

        expires_in_value = payload.get("expires_in", 0)
        expires_in = 0.0
        try:
            expires_in = float(expires_in_value)
        except (TypeError, ValueError):
            expires_in = 0.0
        if not isfinite(expires_in) or expires_in <= 0.0:
            expires_in = 60.0

        self._oauth_access_token = access_token
        self._oauth_access_token_expires_at_unix = now + expires_in
        return self._oauth_access_token

    def _runtime_registration_action_path(
        self, path_template: str, registration_id: str
    ) -> str:
        trimmed_id = registration_id.strip()
        if trimmed_id == "":
            raise ValueError(
                "simpleflow sdk payload error: registration_id is required"
            )
        if "{registration_id}" in path_template:
            return path_template.replace("{registration_id}", trimmed_id)
        if path_template.endswith("/"):
            return f"{path_template}{trimmed_id}"
        return f"{path_template}/{trimmed_id}"

    def _path_with_query(self, path: str, query: dict[str, Any]) -> str:
        encoded = urlencode(query)
        if encoded == "":
            return path
        return f"{path}?{encoded}"

    def _raise_request_error(self, *, path: str, status_code: int, body: str) -> None:
        detail = body.strip()
        if detail == "":
            detail = "request failed"
        if status_code == 401:
            raise SimpleFlowAuthenticationError(
                status_code=status_code,
                detail=detail,
                path=path,
            )
        if status_code == 403:
            raise SimpleFlowAuthorizationError(
                status_code=status_code,
                detail=detail,
                path=path,
            )
        if self._is_lifecycle_path(path):
            raise SimpleFlowLifecycleError(
                status_code=status_code,
                detail=detail,
                path=path,
            )
        raise SimpleFlowRequestError(status_code=status_code, detail=detail, path=path)

    def _is_lifecycle_path(self, path: str) -> bool:
        normalized = path if path.startswith("/") else f"/{path}"
        registration_root = self._runtime_register_path.rstrip("/")
        return normalized.startswith(registration_root)


class TelemetryBridge:
    def __init__(
        self,
        *,
        client: SimpleFlowClient,
        mode: str,
        sample_rate: float | None,
        otlp_sink: Any | None,
        default_trace: dict[str, str] | None,
    ) -> None:
        normalized_mode = mode.strip().lower()
        if normalized_mode not in {"simpleflow", "otlp"}:
            raise ValueError(
                "simpleflow sdk config error: telemetry mode must be one of simpleflow or otlp"
            )
        _validate_sample_rate(sample_rate)
        self._client = client
        self._mode = normalized_mode
        self._sample_rate = sample_rate
        self._otlp_sink = otlp_sink
        self._default_trace = default_trace if default_trace is not None else {}

    def emit_span(
        self,
        *,
        span: Any,
        agent_id: str = "",
        run_id: str = "",
        trace_id: str = "",
        request_id: str = "",
        conversation_id: str = "",
    ) -> None:
        normalized_span = _normalize_payload(span)
        if trace_id.strip() != "" and not _should_sample(trace_id, self._sample_rate):
            return

        if self._mode == "otlp":
            if callable(self._otlp_sink):
                self._otlp_sink(normalized_span)
            return

        fallback_agent_id = str(self._default_trace.get("agent_id", "")).strip()
        fallback_run_id = str(self._default_trace.get("run_id", "")).strip()
        fallback_request_id = str(self._default_trace.get("request_id", "")).strip()
        fallback_conversation_id = str(
            self._default_trace.get("conversation_id", "")
        ).strip()

        self._client.write_event(
            {
                "type": "runtime.telemetry.span",
                "agent_id": agent_id.strip()
                if agent_id.strip() != ""
                else fallback_agent_id,
                "run_id": run_id.strip() if run_id.strip() != "" else fallback_run_id,
                "request_id": request_id.strip()
                if request_id.strip() != ""
                else fallback_request_id,
                "conversation_id": conversation_id.strip()
                if conversation_id.strip() != ""
                else fallback_conversation_id,
                "trace_id": trace_id.strip(),
                "sampled": True,
                "payload": {"span": normalized_span},
            }
        )

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from math import isfinite
from typing import Any

import httpx


def _normalize_payload(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if hasattr(payload, "__dataclass_fields__"):
        return asdict(payload)
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
        runtime_register_path: str = "/v1/runtime/registrations",
        runtime_invoke_path: str = "/v1/runtime/invoke",
        runtime_events_path: str = "/v1/runtime/events",
        runtime_activate_path: str = "/v1/runtime/registrations/{registration_id}/activate",
        runtime_deactivate_path: str = "/v1/runtime/registrations/{registration_id}/deactivate",
        runtime_validate_path: str = "/v1/runtime/registrations/{registration_id}/validate",
        chat_messages_path: str = "/v1/runtime/chat/messages",
        queue_contracts_path: str = "/v1/runtime/queue/contracts",
        chat_history_path: str = "/v1/chat/history/messages",
        timeout_seconds: float = 10.0,
    ) -> None:
        if base_url.strip() == "":
            raise ValueError("simpleflow sdk config error: base_url is required")
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token.strip() if api_token is not None else ""
        self._runtime_register_path = runtime_register_path
        self._runtime_invoke_path = runtime_invoke_path
        self._runtime_events_path = runtime_events_path
        self._runtime_activate_path = runtime_activate_path
        self._runtime_deactivate_path = runtime_deactivate_path
        self._runtime_validate_path = runtime_validate_path
        self._chat_messages_path = chat_messages_path
        self._queue_contracts_path = queue_contracts_path
        self._chat_history_path = chat_history_path
        self._client = httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def register_runtime(self, registration: Any) -> dict[str, Any]:
        return self._post(self._runtime_register_path, registration)

    def activate_runtime_registration(self, registration_id: str) -> None:
        self._post(
            self._runtime_registration_action_path(
                self._runtime_activate_path, registration_id
            ),
            {},
        )

    def deactivate_runtime_registration(self, registration_id: str) -> None:
        self._post(
            self._runtime_registration_action_path(
                self._runtime_deactivate_path, registration_id
            ),
            {},
        )

    def validate_runtime_registration(self, registration_id: str) -> dict[str, Any]:
        return self._post(
            self._runtime_registration_action_path(
                self._runtime_validate_path, registration_id
            ),
            {},
        )

    def invoke(self, request: Any) -> dict[str, Any]:
        response = self._post(self._runtime_invoke_path, request)
        return response

    def write_event(self, event: Any) -> None:
        body = _normalize_payload(event)
        event_type = str(body.get("event_type", "")).strip()
        if event_type == "":
            event_type = str(body.get("type", "")).strip()
        body["event_type"] = event_type
        body.pop("type", None)
        idempotency_key = str(body.pop("idempotency_key", "")).strip()
        headers: dict[str, str] = {}
        if idempotency_key != "":
            headers["Idempotency-Key"] = idempotency_key
        self._post(self._runtime_events_path, body, extra_headers=headers)

    def report_runtime_event(self, event: Any) -> None:
        self.write_event(event)

    def write_chat_message(self, message: Any) -> None:
        body = _normalize_payload(message)
        idempotency_key = str(body.pop("idempotency_key", "")).strip()
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
        self, *, agent_id: str, chat_id: str, user_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        path = f"{self._chat_history_path}?agent_id={agent_id}&chat_id={chat_id}&user_id={user_id}&limit={limit}"
        response = self._get(path)
        messages = response.get("messages")
        if isinstance(messages, list):
            return [item for item in messages if isinstance(item, dict)]
        return []

    def create_chat_history_message(self, message: Any) -> dict[str, Any]:
        return self._post(self._chat_history_path, message)

    def update_chat_history_message(
        self,
        *,
        message_id: str,
        agent_id: str,
        chat_id: str,
        user_id: str,
        content: Any,
        metadata: Any,
    ) -> dict[str, Any]:
        payload = {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "content": _normalize_payload(content),
            "metadata": _normalize_payload(metadata),
        }
        return self._patch(f"{self._chat_history_path}/{message_id}", payload)

    def write_event_from_workflow_result(
        self,
        *,
        agent_id: str,
        workflow_result: Any,
        event_type: str = "runtime.workflow.completed",
    ) -> None:
        normalized_result = _normalize_payload(workflow_result)
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
        trace_id = str(telemetry_dict.get("trace_id", "")).strip()
        sampled_value = telemetry_dict.get("sampled")
        sampled = sampled_value if isinstance(sampled_value, bool) else None

        self.write_event(
            {
                "event_type": event_type,
                "agent_id": agent_id,
                "run_id": run_id,
                "conversation_id": conversation_id,
                "request_id": request_id,
                "trace_id": trace_id,
                "sampled": sampled,
                "payload": normalized_result,
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
    ) -> dict[str, Any]:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self._base_url}{normalized_path}"
        body = _normalize_payload(payload)

        headers = {"Content-Type": "application/json"}
        if self._api_token != "":
            headers["Authorization"] = f"Bearer {self._api_token}"
        if extra_headers is not None:
            headers.update(extra_headers)

        response = self._client.post(url, json=body, headers=headers)
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(
                f"simpleflow sdk request error: status={response.status_code} body={response.text.strip()}"
            )
        if response.text.strip() == "":
            return {}
        try:
            decoded = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "simpleflow sdk request error: expected JSON response body"
            ) from exc
        if isinstance(decoded, dict):
            return decoded
        raise RuntimeError(
            "simpleflow sdk request error: expected JSON object response body"
        )

    def _get(self, path: str) -> dict[str, Any]:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self._base_url}{normalized_path}"
        headers: dict[str, str] = {}
        if self._api_token != "":
            headers["Authorization"] = f"Bearer {self._api_token}"
        response = self._client.get(url, headers=headers)
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(
                f"simpleflow sdk request error: status={response.status_code} body={response.text.strip()}"
            )
        if response.text.strip() == "":
            return {}
        decoded = response.json()
        if isinstance(decoded, dict):
            return decoded
        raise RuntimeError(
            "simpleflow sdk request error: expected JSON object response body"
        )

    def _patch(self, path: str, payload: Any) -> dict[str, Any]:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self._base_url}{normalized_path}"
        body = _normalize_payload(payload)
        headers = {"Content-Type": "application/json"}
        if self._api_token != "":
            headers["Authorization"] = f"Bearer {self._api_token}"
        response = self._client.patch(url, json=body, headers=headers)
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(
                f"simpleflow sdk request error: status={response.status_code} body={response.text.strip()}"
            )
        if response.text.strip() == "":
            return {}
        decoded = response.json()
        if isinstance(decoded, dict):
            return decoded
        raise RuntimeError(
            "simpleflow sdk request error: expected JSON object response body"
        )

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

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import httpx


class SimpleFlowClient:
    def __init__(
        self,
        base_url: str,
        api_token: str | None = None,
        runtime_events_path: str = "/v1/runtime/events",
        chat_messages_path: str = "/v1/runtime/chat/messages",
        queue_contracts_path: str = "/v1/runtime/queue/contracts",
        timeout_seconds: float = 10.0,
    ) -> None:
        if base_url.strip() == "":
            raise ValueError("simpleflow sdk config error: base_url is required")
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token.strip() if api_token is not None else ""
        self._runtime_events_path = runtime_events_path
        self._chat_messages_path = chat_messages_path
        self._queue_contracts_path = queue_contracts_path
        self._client = httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def report_runtime_event(self, event: Any) -> None:
        self._post(self._runtime_events_path, event)

    def write_chat_message(self, message: Any) -> None:
        self._post(self._chat_messages_path, message)

    def publish_queue_contract(self, contract: Any) -> None:
        self._post(self._queue_contracts_path, contract)

    def _post(self, path: str, payload: Any) -> None:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self._base_url}{normalized_path}"
        body = self._normalize_payload(payload)

        headers = {"Content-Type": "application/json"}
        if self._api_token != "":
            headers["Authorization"] = f"Bearer {self._api_token}"

        response = self._client.post(url, json=body, headers=headers)
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(
                f"simpleflow sdk request error: status={response.status_code} body={response.text.strip()}"
            )

    @staticmethod
    def _normalize_payload(payload: Any) -> dict[str, Any]:
        if hasattr(payload, "__dataclass_fields__"):
            return asdict(payload)
        if isinstance(payload, dict):
            return payload
        raise TypeError(
            "simpleflow sdk payload error: payload must be a dataclass or dict"
        )

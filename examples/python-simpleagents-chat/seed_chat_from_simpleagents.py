from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SDK_PATH = REPO_ROOT / "python"
if str(PYTHON_SDK_PATH) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK_PATH))

from simpleflow_sdk import SimpleFlowClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a SimpleAgents workflow and seed chat/session records in SimpleFlow control plane."
    )
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--email", default=os.getenv("SIMPLEFLOW_USER_EMAIL", ""))
    parser.add_argument("--password", default=os.getenv("SIMPLEFLOW_USER_PASSWORD", ""))
    parser.add_argument("--agent-id", default=os.getenv("SIMPLEFLOW_AGENT_ID", ""))
    parser.add_argument("--chat-id", default="")
    parser.add_argument(
        "--user-input",
        default="Please classify this invoice and summarize key findings.",
    )
    parser.add_argument(
        "--workflow-file",
        default=os.getenv("WORKFLOW_PATH", ""),
        help="Path to YAML workflow for simple-agents-py typed execution.",
    )
    parser.add_argument(
        "--workflow-result-file",
        default=str(Path(__file__).resolve().parent / "sample_workflow_result.json"),
        help="Optional JSON result file fallback; skips live workflow when present.",
    )
    parser.add_argument(
        "--use-live-workflow",
        action="store_true",
        help="Run live simple-agents workflow instead of loading workflow-result-file.",
    )
    return parser.parse_args()


def build_chat_id(explicit_chat_id: str) -> str:
    if explicit_chat_id.strip() != "":
        return explicit_chat_id.strip()
    return f"sdk_demo_{uuid.uuid4().hex[:10]}"


def _read_json_file(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("workflow result file must contain a JSON object")
    return parsed


def run_simple_agents_workflow(workflow_file: Path, user_input: str) -> dict[str, Any]:
    try:
        from simple_agents_py import Client as SimpleAgentsClient
        from simple_agents_py.workflow_payload import (
            workflow_execution_request_to_mapping,
        )
        from simple_agents_py.workflow_request import (
            WorkflowExecutionRequest,
            WorkflowMessage,
            WorkflowRole,
        )
    except Exception as exc:  # pragma: no cover - runtime dependency guard
        raise RuntimeError(
            "simple-agents-py is required for --use-live-workflow. Install from SimpleAgents examples workspace."
        ) from exc

    provider = os.getenv("WORKFLOW_PROVIDER", "").strip()
    api_base = os.getenv("WORKFLOW_API_BASE", "").strip()
    api_key = os.getenv("WORKFLOW_API_KEY", "").strip()
    if provider == "" or api_base == "" or api_key == "":
        raise RuntimeError(
            "WORKFLOW_PROVIDER, WORKFLOW_API_BASE, and WORKFLOW_API_KEY are required for --use-live-workflow"
        )

    if not workflow_file.exists():
        raise RuntimeError(f"workflow file not found: {workflow_file}")

    client = SimpleAgentsClient(provider, api_base=api_base, api_key=api_key)
    request = WorkflowExecutionRequest(
        workflow_path=str(workflow_file),
        messages=[WorkflowMessage(role=WorkflowRole.USER, content=user_input)],
    )
    result = client.run_workflow(workflow_execution_request_to_mapping(request))
    if not isinstance(result, dict):
        raise RuntimeError("simple-agents workflow result must be a JSON object")
    return result


async def discover_agent_id(base_url: str, token: str) -> str:
    async with httpx.AsyncClient(timeout=15.0) as http:
        response = await http.get(
            f"{base_url.rstrip('/')}/api/v1/agents",
            headers={"Authorization": f"Bearer {token}"},
        )
    response.raise_for_status()
    payload = response.json()
    agents: list[Any] = []
    if isinstance(payload, list):
        agents = payload
    elif isinstance(payload, dict):
        for key in ("agents", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                agents = value
                break
    else:
        raise RuntimeError("unexpected /api/v1/agents response payload")

    if not agents:
        raise RuntimeError(
            "no agents returned by /api/v1/agents; pass --agent-id explicitly"
        )
    for item in agents:
        if not isinstance(item, dict):
            continue
        for key in ("id", "ID", "agent_id"):
            value = item.get(key)
            if isinstance(value, str) and value.strip() != "":
                return value
    raise RuntimeError("could not resolve an agent id from /api/v1/agents response")


async def main() -> None:
    args = parse_args()
    if args.email.strip() == "" or args.password.strip() == "":
        raise RuntimeError(
            "email and password are required (set --email/--password or SIMPLEFLOW_USER_* env vars)"
        )

    workflow_result: dict[str, Any]
    if args.use_live_workflow:
        if args.workflow_file.strip() == "":
            raise RuntimeError(
                "--workflow-file is required when --use-live-workflow is set"
            )
        workflow_result = run_simple_agents_workflow(
            Path(args.workflow_file).expanduser().resolve(),
            args.user_input,
        )
    else:
        result_file = Path(args.workflow_result_file).expanduser().resolve()
        workflow_result = _read_json_file(result_file)

    client = SimpleFlowClient(base_url=args.base_url)
    session = await client.create_auth_session(email=args.email, password=args.password)
    access_token = str(session.get("access_token", "")).strip()
    if access_token == "":
        raise RuntimeError("login succeeded but no access_token returned")

    principal = await client.validate_access_token(auth_token=access_token)
    user_id = str(principal.get("user_id", "")).strip()
    if user_id == "":
        user_id = str((session.get("user") or {}).get("id", "")).strip()
    if user_id == "":
        raise RuntimeError(
            "could not resolve user_id from /v1/me or auth session response"
        )

    agent_id = args.agent_id.strip()
    if agent_id == "":
        agent_id = await discover_agent_id(args.base_url, access_token)

    chat_id = build_chat_id(args.chat_id)
    user_message_id = f"user_{uuid.uuid4().hex[:10]}"
    assistant_message_id = f"assistant_{uuid.uuid4().hex[:10]}"

    await client.write_chat_message(
        {
            "agent_id": agent_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "message_id": user_message_id,
            "role": "user",
            "content": {"text": args.user_input},
            "telemetry_data": {"source": "sdk-example", "event_type": "user.message"},
        },
        auth_token=access_token,
    )

    await client.write_chat_message_from_simple_agents_result(
        agent_id=agent_id,
        user_id=user_id,
        chat_id=chat_id,
        message_id=assistant_message_id,
        workflow_result=workflow_result,
        auth_token=access_token,
    )

    messages = await client.list_chat_messages(
        agent_id=agent_id,
        chat_id=chat_id,
        user_id=user_id,
        auth_token=access_token,
    )
    sessions = await client.list_chat_sessions(
        agent_id=agent_id,
        user_id=user_id,
        auth_token=access_token,
    )
    output = await client.get_chat_message_output(
        message_id=assistant_message_id,
        agent_id=agent_id,
        chat_id=chat_id,
        user_id=user_id,
        auth_token=access_token,
    )

    print(
        json.dumps(
            {
                "base_url": args.base_url,
                "agent_id": agent_id,
                "user_id": user_id,
                "chat_id": chat_id,
                "user_message_id": user_message_id,
                "assistant_message_id": assistant_message_id,
                "messages_count": len(messages),
                "sessions_count": len(sessions),
                "output_keys": sorted((output.get("output") or {}).keys()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())

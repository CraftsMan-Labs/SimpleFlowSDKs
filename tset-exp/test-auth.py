import os
import httpx
import asyncio
from simpleflow_sdk import SimpleFlowClient
async def get_user_token(email: str, password: str) -> str:
    base = os.environ["SIMPLEFLOW_BASE_URL"].rstrip("/")
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.post(
            f"{base}/v1/auth/sessions",
            json={"email": email, "password": password},
        )
        r.raise_for_status()
        return r.json()["access_token"]
async def main():
    user_token = await get_user_token("john@example.com", "your-password")
    client = SimpleFlowClient(
        base_url=os.environ["SIMPLEFLOW_BASE_URL"],
        api_token=os.environ["SIMPLEFLOW_API_TOKEN"],  # optional default machine token
    )
    sessions = await client.list_chat_sessions(
        agent_id=os.environ["SIMPLEFLOW_AGENT_ID"],
        user_id=os.environ["SIMPLEFLOW_USER_ID"],
        auth_token=user_token,  # user JWT
    )
    print(sessions)
    await client.close()
asyncio.run(main())
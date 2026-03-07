from __future__ import annotations

from typing import Any

import jwt


class InvokeTokenVerifier:
    def __init__(
        self, issuer: str, audience: str, algorithms: list[str] | None = None
    ) -> None:
        if issuer.strip() == "":
            raise ValueError("simpleflow sdk auth config error: issuer is required")
        if audience.strip() == "":
            raise ValueError("simpleflow sdk auth config error: audience is required")

        self._issuer = issuer
        self._audience = audience
        self._algorithms = algorithms if algorithms is not None else ["HS256", "RS256"]

    def verify(self, token: str, key: str | bytes | Any) -> dict[str, Any]:
        if token.strip() == "":
            raise ValueError("simpleflow sdk auth error: token is required")

        claims = jwt.decode(
            token,
            key=key,
            algorithms=self._algorithms,
            audience=self._audience,
            issuer=self._issuer,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )

        if (
            str(claims.get("agent_id", "")).strip() == ""
            or str(claims.get("org_id", "")).strip() == ""
        ):
            raise ValueError(
                "simpleflow sdk auth error: token missing required agent_id or org_id"
            )

        return claims

from __future__ import annotations

from typing import Any

import jwt


class InvokeTokenVerifier:
    """Verify invoke tokens using HS256 shared keys or RS256 public keys.

    You can pass a verification key per call via ``verify(token, key=...)`` or
    configure a default key using ``for_hs256_shared_key`` / ``for_rs256_public_key``.
    """

    def __init__(
        self,
        issuer: str,
        audience: str,
        algorithms: list[str] | None = None,
        verification_key: str | bytes | Any | None = None,
    ) -> None:
        if issuer.strip() == "":
            raise ValueError("simpleflow sdk auth config error: issuer is required")
        if audience.strip() == "":
            raise ValueError("simpleflow sdk auth config error: audience is required")

        self._issuer = issuer
        self._audience = audience
        self._algorithms = algorithms if algorithms is not None else ["HS256", "RS256"]
        self._verification_key = verification_key

    @classmethod
    def for_hs256_shared_key(
        cls,
        *,
        issuer: str,
        audience: str,
        shared_key: str | bytes,
    ) -> "InvokeTokenVerifier":
        return cls(
            issuer=issuer,
            audience=audience,
            algorithms=["HS256"],
            verification_key=shared_key,
        )

    @classmethod
    def for_rs256_public_key(
        cls,
        *,
        issuer: str,
        audience: str,
        public_key: str | bytes,
    ) -> "InvokeTokenVerifier":
        return cls(
            issuer=issuer,
            audience=audience,
            algorithms=["RS256"],
            verification_key=public_key,
        )

    def verify(
        self, token: str, key: str | bytes | Any | None = None
    ) -> dict[str, Any]:
        if token.strip() == "":
            raise ValueError("simpleflow sdk auth error: token is required")
        verification_key = key if key is not None else self._verification_key
        if verification_key is None:
            raise ValueError("simpleflow sdk auth error: verification key is required")

        claims = jwt.decode(
            token,
            key=verification_key,
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

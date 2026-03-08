from __future__ import annotations

import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import sys
import time
import types


def _as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _jwt_encode(payload: dict, key: str | bytes, algorithm: str) -> str:
    return json.dumps(
        {
            "payload": payload,
            "key": _as_text(key),
            "alg": algorithm,
        }
    )


def _jwt_decode(
    token: str,
    *,
    key: str | bytes,
    algorithms: list[str],
    audience: str,
    issuer: str,
    options: dict,
) -> dict:
    del options
    decoded = json.loads(token)
    if decoded.get("alg") not in algorithms:
        raise ValueError("invalid algorithm")
    if decoded.get("key") != _as_text(key):
        raise ValueError("signature verification failed")
    payload = decoded.get("payload", {})
    if payload.get("iss") != issuer:
        raise ValueError("invalid issuer")
    if payload.get("aud") != audience:
        raise ValueError("invalid audience")
    return payload


jwt_stub = types.ModuleType("jwt")
setattr(jwt_stub, "encode", _jwt_encode)
setattr(jwt_stub, "decode", _jwt_decode)
sys.modules.setdefault("jwt", jwt_stub)

AUTH_MODULE_PATH = Path(__file__).resolve().parent.parent / "simpleflow_sdk" / "auth.py"
AUTH_SPEC = spec_from_file_location("simpleflow_sdk_auth", AUTH_MODULE_PATH)
if AUTH_SPEC is None or AUTH_SPEC.loader is None:
    raise RuntimeError("failed to load simpleflow sdk auth module for tests")
AUTH_MODULE = module_from_spec(AUTH_SPEC)
AUTH_SPEC.loader.exec_module(AUTH_MODULE)
InvokeTokenVerifier = AUTH_MODULE.InvokeTokenVerifier


class InvokeTokenVerifierTests(unittest.TestCase):
    def test_hs256_shared_key_helper_verifies_token(self) -> None:
        verifier = InvokeTokenVerifier.for_hs256_shared_key(
            issuer="simpleflow",
            audience="runtime",
            shared_key="local-secret",
        )
        token = jwt_stub.encode(
            {
                "iss": "simpleflow",
                "aud": "runtime",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
                "agent_id": "agent_1",
                "org_id": "org_1",
            },
            "local-secret",
            algorithm="HS256",
        )

        claims = verifier.verify(token)
        self.assertEqual(claims["agent_id"], "agent_1")
        self.assertEqual(claims["org_id"], "org_1")

    def test_verify_requires_key_when_default_not_configured(self) -> None:
        verifier = InvokeTokenVerifier(issuer="simpleflow", audience="runtime")
        token = jwt_stub.encode(
            {
                "iss": "simpleflow",
                "aud": "runtime",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
                "agent_id": "agent_1",
                "org_id": "org_1",
            },
            "local-secret",
            algorithm="HS256",
        )

        with self.assertRaisesRegex(ValueError, "verification key is required"):
            verifier.verify(token)


if __name__ == "__main__":
    unittest.main()

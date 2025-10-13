"""Very small JWT helper supporting HS256 signing.

This avoids the need for ``python-jose`` in the constrained execution
environment while still providing compatible tokens for the FastAPI layer.
"""

from __future__ import annotations

import base64
import json
import hmac
import hashlib
import time
from typing import Iterable, Mapping


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def encode_jwt(
    payload: Mapping[str, object], secret: str, *, algorithm: str = "HS256"
) -> str:
    if algorithm != "HS256":
        raise ValueError("Only HS256 is supported by the lightweight encoder")
    header = {"alg": algorithm, "typ": "JWT"}
    header_segment = _b64encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_segment = _b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_segment = _b64encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def decode_jwt(
    token: str, secret: str, *, algorithms: Iterable[str] | None = None
) -> dict:
    if algorithms is not None and "HS256" not in set(algorithms):
        raise ValueError("Unsupported algorithm requested")
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise ValueError("Invalid token format") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = hmac.new(
        secret.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    actual_signature = _b64decode(signature_segment)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise ValueError("Signature mismatch")

    payload = json.loads(_b64decode(payload_segment))
    exp = payload.get("exp")
    if exp is not None:
        if not isinstance(exp, (int, float)):
            raise ValueError("Invalid exp claim")
        if exp < time.time():
            raise ValueError("Token has expired")
    return payload

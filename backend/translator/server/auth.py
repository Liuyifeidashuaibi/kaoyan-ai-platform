"""API Key authentication for internal service calls."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status

from translator.server.responses import error_response


def _expected_api_key() -> str:
    return os.environ.get("TRANSLATOR_API_KEY", "").strip()


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = _expected_api_key()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_response(
                "TRANSLATOR_API_KEY is not configured on the server",
                error_code="AUTH_NOT_CONFIGURED",
            ),
        )
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response("Invalid or missing API key", error_code="UNAUTHORIZED"),
        )

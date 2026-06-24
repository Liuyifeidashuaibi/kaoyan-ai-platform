"""Standard JSON response helpers for the HTTP API."""

from __future__ import annotations

from typing import Any


def success_response(data: Any = None, message: str = "") -> dict[str, Any]:
    return {"success": True, "data": data, "message": message}


def error_response(
    message: str,
    *,
    error_code: str = "INTERNAL_ERROR",
    data: Any = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "data": data,
        "message": message,
        "error_code": error_code,
    }

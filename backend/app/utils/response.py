"""
统一 API 响应格式工具。

所有接口返回：{"success": true, "data": {}, "message": ""}
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """标准 API 响应模型。"""

    success: bool = True
    data: T | None = None
    message: str = ""


def success_response(data: Any = None, message: str = "") -> dict:
    """构造成功响应。"""
    return {"success": True, "data": data, "message": message}


def error_response(message: str, data: Any = None) -> dict:
    """构造失败响应。"""
    return {"success": False, "data": data, "message": message}

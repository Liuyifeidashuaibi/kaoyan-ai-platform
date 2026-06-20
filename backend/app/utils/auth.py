"""
Supabase JWT 鉴权 — 供社区等需登录接口使用。
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Header, HTTPException

from app.config import get_settings
from app.utils.jwt_verify import jwt_sub as verified_jwt_sub

logger = logging.getLogger(__name__)

DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _decode_jwt_sub(token: str) -> str | None:
    """从 Supabase access token 解析 user id。"""
    return verified_jwt_sub(token)


def resolve_user_id(authorization: str | None) -> str | None:
    """解析 JWT 得到 user id；开发环境无 Supabase 时允许 dev 用户。"""
    token = _extract_bearer(authorization)
    settings = get_settings()

    if not token:
        return None

    if token == "dev":
        if not settings.effective_supabase_url or not settings.effective_supabase_service_key:
            return DEV_USER_ID
        return None

    user_id = _decode_jwt_sub(token)
    if user_id:
        return user_id

    if not settings.effective_supabase_url or not settings.effective_supabase_service_key:
        return None

    try:
        from supabase import create_client

        client = create_client(
            settings.effective_supabase_url,
            settings.effective_supabase_service_key,
        )
        resp = client.auth.get_user(token)
        user = resp.user if resp else None
        if user and user.id:
            return user.id
    except Exception:
        logger.debug("JWT 解析失败", exc_info=True)

    return None


def require_user_id(authorization: Annotated[str | None, Header()] = None) -> str:
    user_id = resolve_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    return user_id


def optional_user_id(authorization: Annotated[str | None, Header()] = None) -> str | None:
    return resolve_user_id(authorization)

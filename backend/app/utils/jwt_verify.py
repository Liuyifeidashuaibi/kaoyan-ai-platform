"""Supabase JWT 校验与解析。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


def decode_supabase_jwt(token: str) -> dict[str, Any] | None:
    """解析 Supabase access token；配置了 JWT secret 时校验签名与过期。"""
    try:
        import jwt
    except ImportError:
        logger.error("PyJWT 未安装")
        return None

    settings = get_settings()
    secret = settings.effective_supabase_jwt_secret

    if secret:
        try:
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError:
            logger.debug("JWT 签名校验失败", exc_info=True)
            return None

    # 未配置 secret：仅开发环境允许无签名校验
    import os

    if os.environ.get("NODE_ENV") == "production":
        return None

    try:
        return jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_exp": False,
            },
        )
    except jwt.PyJWTError:
        return None


def jwt_sub(token: str) -> str | None:
    payload = decode_supabase_jwt(token)
    if not payload:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


def jwt_email(token: str) -> str | None:
    payload = decode_supabase_jwt(token)
    if not payload:
        return None
    email = payload.get("email")
    return str(email).lower() if email else None

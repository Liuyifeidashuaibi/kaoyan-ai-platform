"""管理后台鉴权。"""

from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import Header, HTTPException

from app.config import get_settings
from app.utils.auth import _extract_bearer
from app.utils.jwt_verify import jwt_email, jwt_sub

logger = logging.getLogger(__name__)


def _should_skip_auth_in_dev() -> bool:
    if os.environ.get("NODE_ENV") == "production":
        return False
    if os.environ.get("SKIP_AUTH_IN_DEV", "").lower() == "true":
        return True
    if os.environ.get("NEXT_PUBLIC_SKIP_AUTH_IN_DEV", "").lower() == "true":
        return True
    return not get_settings().effective_supabase_url


def _admin_emails() -> set[str]:
    settings = get_settings()
    raw = settings.admin_emails.strip() or os.environ.get("NEXT_PUBLIC_ADMIN_EMAILS", "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def require_admin(authorization: Annotated[str | None, Header()] = None) -> str:
    """校验管理员身份，返回 user id 或 dev。"""
    token = _extract_bearer(authorization)
    admins = _admin_emails()

    if token == "dev":
        if os.environ.get("NODE_ENV") != "production":
            return "dev-admin"
        raise HTTPException(status_code=401, detail="无效的开发令牌")

    if not token:
        if not admins and _should_skip_auth_in_dev():
            return "dev-admin"
        raise HTTPException(status_code=401, detail="请先登录")

    user_id = jwt_sub(token)
    email = jwt_email(token)

    if not user_id and not email:
        raise HTTPException(status_code=401, detail="登录已过期或无效")

    if admins:
        if email and email in admins:
            return user_id or email
        raise HTTPException(status_code=403, detail="无管理权限")

    if os.environ.get("NODE_ENV") != "production" and _should_skip_auth_in_dev():
        return user_id or "dev-admin"

    raise HTTPException(status_code=403, detail="未配置 ADMIN_EMAILS")

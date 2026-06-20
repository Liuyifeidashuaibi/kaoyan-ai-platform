"""
用户会员额度 Redis 缓存 — 本地测试用轻量配额模型。

不改动原有业务 Service；翻译/聊天等路由可在扣减前 consult 此模块。
默认：普通用户每日翻译 50 次、AI 问答 200 次（可通过 .env 调整）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.infrastructure.cache import keys
from app.infrastructure.cache.redis_client import cache_get_json, cache_set_json, is_redis_enabled

logger = logging.getLogger(__name__)


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now.hour or now.minute or now.second:
        from datetime import timedelta

        tomorrow = tomorrow + timedelta(days=1)
    return max(60, int((tomorrow - now).total_seconds()))


class MembershipQuotaCache:
    """按用户缓存当日额度使用情况。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.daily_translate_limit = settings.membership_daily_translate_limit
        self.daily_chat_limit = settings.membership_daily_chat_limit
        self.ttl = settings.cache_ttl_membership_quota

    def _default_quota(self, user_id: str) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "tier": "standard",
            "translate_used": 0,
            "translate_limit": self.daily_translate_limit,
            "chat_used": 0,
            "chat_limit": self.daily_chat_limit,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_quota(self, user_id: str) -> dict[str, Any]:
        """读取用户额度（Redis 未启用时返回内存默认值，不阻断业务）。"""
        if not is_redis_enabled():
            return self._default_quota(user_id)

        key = keys.membership_quota_key(user_id)
        cached = cache_get_json(key)
        if cached is None:
            quota = self._default_quota(user_id)
            cache_set_json(key, quota, min(self.ttl, _seconds_until_utc_midnight()))
            return quota
        return cached

    def check_and_consume(self, user_id: str, kind: str, amount: int = 1) -> tuple[bool, dict[str, Any]]:
        """
        检查并扣减额度。kind: translate | chat
        返回 (allowed, quota_snapshot)
        """
        quota = self.get_quota(user_id)
        if kind == "translate":
            used_key = "translate_used"
            limit_key = "translate_limit"
        elif kind == "chat":
            used_key = "chat_used"
            limit_key = "chat_limit"
        else:
            return True, quota

        used = int(quota.get(used_key, 0))
        limit = int(quota.get(limit_key, self.daily_translate_limit))
        if used + amount > limit:
            return False, quota

        quota[used_key] = used + amount
        quota["updated_at"] = datetime.now(timezone.utc).isoformat()

        if is_redis_enabled():
            key = keys.membership_quota_key(user_id)
            cache_set_json(key, quota, min(self.ttl, _seconds_until_utc_midnight()))
        return True, quota


_quota: MembershipQuotaCache | None = None


def get_membership_quota_cache() -> MembershipQuotaCache:
    global _quota
    if _quota is None:
        _quota = MembershipQuotaCache()
    return _quota

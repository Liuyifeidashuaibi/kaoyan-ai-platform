#!/usr/bin/env python3
"""
Redis 缓存本地测试 — 在项目根目录执行:
  python examples/test_redis_cache.py

需 Redis 运行且 .env 配置 REDIS_URL。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local")

from app.infrastructure.cache.redis_client import cache_set_json, cache_get_json, is_redis_enabled
from app.infrastructure.cache import keys
from app.services.response_cache import get_response_cache


def main() -> None:
    print("=== Redis 缓存测试 ===\n")

    if not is_redis_enabled():
        print("❌ Redis 不可用，请启动 Redis 并配置 REDIS_URL=redis://127.0.0.1:6379/0")
        sys.exit(1)
    print("✅ Redis 连接正常\n")

    # 1. 基础 JSON 读写 + TTL
    test_key = "kaoyan:test:ping"
    cache_set_json(test_key, {"hello": "world"}, 60)
    val = cache_get_json(test_key)
    assert val == {"hello": "world"}, val
    print("✅ JSON 缓存读写 OK")

    # 2. AI 问答缓存（ResponseCache → Redis）
    rc = get_response_cache()
    q = "什么是考研国家线？"
    rc.set(q, "国家线是教育部划定的最低复试资格线。")
    hit = rc.get(q)
    assert hit and "国家线" in hit, hit
    print("✅ AI 问答缓存 OK:", hit[:40], "…")

    # 3. Key 生成
    k = keys.schools_list_key(1, None, "985", 20)
    print("✅ 院校列表 Key 示例:", k)

    # 4. 会员额度
    from app.infrastructure.cache.membership_quota import get_membership_quota_cache

    quota = get_membership_quota_cache().get_quota("test-user-001")
    print("✅ 会员额度缓存:", quota)

    print("\n全部测试通过。")


if __name__ == "__main__":
    main()

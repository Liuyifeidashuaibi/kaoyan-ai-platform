"""爬虫完成后 bump schools_sync_meta.revision，通知前端刷新择校数据"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pathlib import Path
from supabase import create_client

load_dotenv(Path(__file__).parent / ".env")
load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger("notify_frontend")


def bump_schools_sync(note: str = "crawler") -> int | None:
    """递增 revision，返回新版本号；失败返回 None"""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        log.warning("缺少 Supabase 配置，跳过前端同步通知")
        return None

    sb = create_client(url, key)
    try:
        cur = (
            sb.table("schools_sync_meta")
            .select("revision")
            .eq("id", 1)
            .maybe_single()
            .execute()
        )
        revision = int((cur.data or {}).get("revision") or 0) + 1
        sb.table("schools_sync_meta").upsert(
            {
                "id": 1,
                "revision": revision,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "note": note[:200],
            },
            on_conflict="id",
        ).execute()
        log.info("前端同步 revision → %d (%s)", revision, note)
        return revision
    except Exception as exc:
        log.warning("schools_sync_meta 不可用（请先执行迁移 006）: %s", exc)
        return None


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    note = " ".join(sys.argv[1:]) or "manual"
    bump_schools_sync(note)

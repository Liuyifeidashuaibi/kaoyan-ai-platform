#!/usr/bin/env python3
"""清空 announcements 表并通知前端刷新。"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("purge_ann")


def main() -> None:
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")

    sb = create_client(url, key)
    total = sb.table("announcements").select("id", count="exact").limit(0).execute().count or 0
    log.info("announcements 当前 %d 条，开始清空…", total)

    deleted = 0
    while True:
        res = sb.table("announcements").select("id").limit(200).execute()
        rows = res.data or []
        if not rows:
            break
        ids = [r["id"] for r in rows]
        sb.table("announcements").delete().in_("id", ids).execute()
        deleted += len(ids)
        log.info("已删除 %d/%d …", deleted, total)

    log.info("announcements 已清空，共删除 %d 条", deleted)

    try:
        from notify_frontend import bump_schools_sync

        bump_schools_sync("purge_announcements")
    except Exception as exc:
        log.warning("sync bump 失败: %s", exc)


if __name__ == "__main__":
    main()

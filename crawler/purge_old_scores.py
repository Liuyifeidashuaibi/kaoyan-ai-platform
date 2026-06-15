#!/usr/bin/env python3
"""删除 scores 表中非 2025/2026 年份的记录。"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

from enrich_constants import SCORE_YEARS

_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("purge_old_scores")

KEEP = set(SCORE_YEARS)


def main() -> None:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")

    sb = create_client(url, key)
    deleted = 0

    for year in range(2018, 2030):
        if year in KEEP:
            continue
        while True:
            res = (
                sb.table("scores")
                .select("id")
                .eq("year", year)
                .limit(200)
                .execute()
            )
            rows = res.data or []
            if not rows:
                break
            ids = [r["id"] for r in rows]
            sb.table("scores").delete().in_("id", ids).execute()
            deleted += len(ids)
            log.info("已删除 %d 年 %d 条（累计 %d）", year, len(ids), deleted)

    log.info("清理完成，共删除 %d 条非 %s 年复试线", deleted, sorted(KEEP))

    if deleted > 0:
        from notify_frontend import bump_schools_sync

        bump_schools_sync("purge_old_scores")


if __name__ == "__main__":
    main()

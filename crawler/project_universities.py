"""
择校模块院校清单 — 以 Supabase universities 表为唯一数据源。
爬虫/导入只处理项目内已收录的院校，复试线只绑定已有 majors。
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

log = logging.getLogger("project_universities")


def _client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


@lru_cache(maxsize=1)
def fetch_project_universities() -> list[dict]:
    """返回项目内全部院校（与择校页 universities 表一致）。"""
    sb = _client()
    rows: list[dict] = []
    offset = 0
    while True:
        res = (
            sb.table("universities")
            .select(
                "id,name,province,city,level_985,level_211,double_first_class,school_type,school_code,graduate_url,website"
            )
            .order("name")
            .range(offset, offset + 999)
            .execute()
        )
        batch = res.data or []
        for r in batch:
            rows.append({
                "id": r["id"],
                "name": r["name"],
                "province": r.get("province") or "",
                "city": r.get("city") or "",
                "level_985": bool(r.get("level_985")),
                "level_211": bool(r.get("level_211")),
                "double_first_class": r.get("double_first_class"),
                "school_type": r.get("school_type") or "综合",
                "school_code": r.get("school_code") or "",
                "graduate_url": r.get("graduate_url") or "",
                "website": r.get("website") or "",
            })
        if len(batch) < 1000:
            break
        offset += 1000
    log.info("项目院校 %d 所", len(rows))
    return rows


def project_university_names() -> set[str]:
    return {u["name"] for u in fetch_project_universities()}


def project_university_by_name() -> dict[str, dict]:
    return {u["name"]: u for u in fetch_project_universities()}

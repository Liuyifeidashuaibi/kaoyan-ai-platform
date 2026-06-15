#!/usr/bin/env python3
"""
掌上考研 + 研招网 学院字段批量补全
============================================================
从 zhijiao.cn 院系专业索引、研招网专业目录补全 majors.college。

用法：
  python backfill_colleges_kaoyan.py --limit 2          # 试跑 2 校
  python backfill_colleges_kaoyan.py --school 武汉大学
  python backfill_colleges_kaoyan.py                    # 全部 148 校
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

_here = Path(__file__).parent
sys.path.insert(0, str(_here))
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

from crawl_basic_once import UNIVERSITIES  # noqa: E402
from crawl_kaoyan_scores_csv import (  # noqa: E402
    fetch_chsi_major_index,
    load_school_codes,
)
from kaoyan_score_sources import (  # noqa: E402
    fetch_school_major_index,
    load_school_id_cache,
    resolve_school_id,
    save_school_id_cache,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("backfill_college")

_COLLEGE_RE = re.compile(r"学院|系|中心|部|研究所|研究院|实验室")


def _sb():
    import os
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def _valid_college(college: str) -> bool:
    c = (college or "").strip()
    return bool(c and c != "未知学院" and _COLLEGE_RE.search(c))


def _norm_code(code: str) -> str:
    return re.sub(r"\D", "", code)[:6]


def _norm_name(name: str) -> str:
    return re.sub(r"\s+", "", (name or "").strip())


def build_index(
    kaoyan_majors: list[dict],
    chsi_majors: list[dict],
) -> dict[tuple[str, str], str]:
    """(code6, norm_name) → college，优先更长学院名。"""
    index: dict[tuple[str, str], str] = {}
    for source in (kaoyan_majors, chsi_majors):
        for item in source:
            code = _norm_code(str(item.get("major_code") or ""))
            name = _norm_name(str(item.get("major_name") or ""))
            college = str(item.get("college") or "").strip()
            if len(code) != 6 or not name or not _valid_college(college):
                continue
            key = (code, name)
            prev = index.get(key, "")
            if len(college) > len(prev):
                index[key] = college[:100]
    return index


def lookup_college(
    index: dict[tuple[str, str], str],
    code: str,
    name: str,
) -> Optional[str]:
    code6 = _norm_code(code)
    nname = _norm_name(name)
    if len(code6) == 6:
        hit = index.get((code6, nname))
        if hit:
            return hit
        for (c, n), college in index.items():
            if c == code6 and (n in nname or nname in n):
                return college
    for (c, n), college in index.items():
        if n == nname or (n in nname or nname in n):
            return college
    return None


def get_db_majors(sb, university_id: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        res = (
            sb.table("majors")
            .select("id,code,name,college")
            .eq("university_id", university_id)
            .range(offset, offset + 999)
            .execute()
        )
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return rows


def backfill_school(
    sb,
    session: requests.Session,
    uni: dict,
    uni_id: str,
    school_id_cache: dict[str, int],
    school_codes: dict[str, str],
    *,
    use_chsi: bool,
    dry_run: bool,
) -> int:
    name = uni["name"]
    sid = resolve_school_id(session, name, school_id_cache)
    if not sid:
        log.warning("[%s] 未找到掌上考研 school_id", name)
        return 0

    kaoyan_majors = fetch_school_major_index(session, sid)
    chsi_majors: list[dict] = []
    if use_chsi:
        dwdm = school_codes.get(name, "")
        if dwdm:
            chsi_majors = fetch_chsi_major_index(session, name, dwdm)

    index = build_index(kaoyan_majors, chsi_majors)
    if not index:
        log.info("[%s] 无可用学院索引", name)
        return 0

    db_majors = get_db_majors(sb, uni_id)
    patches: list[tuple[str, str]] = []
    for m in db_majors:
        existing = (m.get("college") or "").strip()
        if _valid_college(existing):
            continue
        college = lookup_college(index, str(m.get("code") or ""), str(m.get("name") or ""))
        if not college:
            continue
        patches.append((m["id"], college))

    updated = len(patches)
    if updated and not dry_run:
        for i in range(0, len(patches), 40):
            chunk = patches[i : i + 40]
            for mid, college in chunk:
                sb.table("majors").update({"college": college}).eq("id", mid).execute()

    if updated:
        log.info("[%s] 学院补全 +%d（索引 %d 条）", name, updated, len(index))
    return updated


def build_uni_id_map(sb) -> dict[str, str]:
    res = sb.table("universities").select("id,name").execute()
    return {(r["name"] or "").strip(): r["id"] for r in (res.data or [])}


def main() -> None:
    parser = argparse.ArgumentParser(description="掌上考研/研招网学院字段补全")
    parser.add_argument("--school", default=None, help="模糊匹配校名")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 所")
    parser.add_argument("--no-chsi", action="store_true", help="不访问研招网")
    parser.add_argument("--dry-run", action="store_true", help="仅统计不写库")
    parser.add_argument("--concurrency", type=int, default=0, help="并行院校数")
    parser.add_argument("--offset", type=int, default=0, help="跳过前 N 所院校")
    args = parser.parse_args()

    schools = UNIVERSITIES
    if args.school:
        schools = [u for u in schools if args.school in u.get("name", "")]
    if args.offset > 0:
        schools = schools[args.offset :]
    if args.limit > 0:
        schools = schools[: args.limit]

    sb = _sb()
    uni_ids = build_uni_id_map(sb)
    school_codes = load_school_codes()
    id_cache = load_school_id_cache()
    cache_lock = threading.Lock()
    total_lock = threading.Lock()
    total = 0

    import os
    concurrency = args.concurrency or (8 if os.environ.get("CRAWLER_FAST") else 1)

    def _one(uni: dict, idx: int) -> int:
        uid = uni_ids.get(uni["name"])
        if not uid:
            log.warning("库内无院校: %s", uni["name"])
            return 0
        log.info("(%d/%d) %s", idx, len(schools), uni["name"])
        session = requests.Session()
        with cache_lock:
            local_cache = dict(id_cache)
        try:
            n = backfill_school(
                sb,
                session,
                uni,
                uid,
                local_cache,
                school_codes,
                use_chsi=not args.no_chsi,
                dry_run=args.dry_run,
            )
            return n
        except Exception as exc:
            log.error("[%s] 失败: %s", uni["name"], exc)
            return 0
        finally:
            with cache_lock:
                id_cache.update(local_cache)
                save_school_id_cache(id_cache)

    if concurrency <= 1:
        for i, uni in enumerate(schools, 1):
            total += _one(uni, i)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(_one, uni, i): uni
                for i, uni in enumerate(schools, 1)
            }
            for fut in as_completed(futures):
                with total_lock:
                    total += fut.result()

    summary = {"schools": len(schools), "colleges_updated": total, "dry_run": args.dry_run}
    log.info("完成: %s", json.dumps(summary, ensure_ascii=False))

    if not args.dry_run and total > 0:
        from notify_frontend import bump_schools_sync

        bump_schools_sync("backfill_colleges_kaoyan")


if __name__ == "__main__":
    main()

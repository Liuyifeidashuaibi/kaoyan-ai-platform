#!/usr/bin/env python3
"""
为分数覆盖率不足的院校，从掌上考研 H5 API 补抓并入库。

用法：
  python fill_low_coverage_scores.py --dry-run
  python fill_low_coverage_scores.py --school 中央音乐学院
  python fill_low_coverage_scores.py --min-coverage 30
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests
from dotenv import load_dotenv

_here = Path(__file__).parent
sys.path.insert(0, str(_here))
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")
load_dotenv(_here.parent / ".env.local")

from enrich_constants import SCORE_YEARS  # noqa: E402
from import_kaoyan_full import (  # noqa: E402
    _sb,
    load_all_majors,
    process_score_items,
)
from db_import_utils import batch_upsert  # noqa: E402
from paths import kaoyan_schools_json  # noqa: E402
from kaoyan_score_sources import fetch_school_score_items  # noqa: E402
from notify_frontend import bump_schools_sync  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fill_low_coverage")

SCHOOLS_JSON = kaoyan_schools_json()
AUDIT_REPORT = _here / "logs" / "audit_scores_report.json"


def load_kaoyan_id_map() -> dict[str, int]:
    if not SCHOOLS_JSON.exists():
        return {}
    with SCHOOLS_JSON.open(encoding="utf-8") as f:
        payload = json.load(f)
    result: dict[str, int] = {}
    for item in payload.get("schools") or []:
        name = (item.get("name") or "").strip()
        sid = item.get("id")
        if name and isinstance(sid, int):
            result[name] = sid
    return result


def load_low_coverage_schools(min_coverage: float) -> list[str]:
    if not AUDIT_REPORT.exists():
        return []
    with AUDIT_REPORT.open(encoding="utf-8") as f:
        report = json.load(f)
    flagged: set[str] = set()
    for issue in report.get("issues") or []:
        pct = issue.get("importable_coverage_pct") or issue.get("db_coverage_pct") or 100
        if pct < min_coverage:
            school = (issue.get("school") or "").strip()
            if school:
                flagged.add(school)
    return sorted(flagged)


def count_importable(
    uid: str,
    majors: list[dict],
    years_data: dict,
    years: set[int],
) -> int:
    rows, _ = process_score_items(uid, majors, years_data, years)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="补抓低覆盖率院校分数")
    parser.add_argument("--school", default="", help="仅处理指定学校")
    parser.add_argument("--min-coverage", type=float, default=30.0, help="覆盖率阈值（%）")
    parser.add_argument("--years", default="2025-2026", help="补分年份")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-notify", action="store_true")
    args = parser.parse_args()

    if "-" in args.years:
        a, b = args.years.split("-", 1)
        allowed_years = {y for y in range(int(a), int(b) + 1) if y in SCORE_YEARS}
    else:
        y = int(args.years)
        allowed_years = {y} if y in SCORE_YEARS else set(SCORE_YEARS)

    kaoyan_ids = load_kaoyan_id_map()
    if args.school:
        targets = [args.school]
    else:
        targets = load_low_coverage_schools(args.min_coverage)

    if not targets:
        log.info("无待补分院校（阈值 %.0f%%）", args.min_coverage)
        return

    sb = _sb()
    res = sb.table("universities").select("id,name").execute()
    uni_lookup = {(r.get("name") or "").strip(): r["id"] for r in (res.data or []) if r.get("name")}
    majors_cache = load_all_majors(sb)
    session = requests.Session()

    total_written = 0
    total_skipped = 0

    for name in targets:
        uid = uni_lookup.get(name)
        kaoyan_id = kaoyan_ids.get(name)
        if not uid:
            log.warning("跳过 %s：Supabase 无此院校", name)
            continue
        if not kaoyan_id:
            log.warning("跳过 %s：无掌上考研 school_id", name)
            continue

        majors = majors_cache.get(uid, [])
        if not majors:
            log.warning("跳过 %s：无专业数据", name)
            continue

        years_data: dict[str, list[dict]] = defaultdict(list)
        for year in sorted(allowed_years):
            items = fetch_school_score_items(session, kaoyan_id, year)
            if items:
                years_data[str(year)] = items
            time.sleep(0.35)

        if not years_data:
            log.warning("%s：H5 无分数数据", name)
            continue

        score_rows, skipped = process_score_items(uid, majors, years_data, allowed_years)
        total_skipped += skipped
        coverage = len(score_rows) / max(len(majors) * len(allowed_years), 1) * 100
        log.info(
            "%s — H5 可入库 %d 条，跳过 %d，约 %.1f%% 覆盖",
            name,
            len(score_rows),
            skipped,
            coverage,
        )

        if args.dry_run or not score_rows:
            continue

        written = batch_upsert(sb, "scores", score_rows, "major_id,year")
        total_written += written

    if not args.dry_run and total_written:
        log.info("补分完成：入库 %d 条，跳过 %d", total_written, total_skipped)
        if not args.no_notify:
            rev = bump_schools_sync("fill_low_coverage_scores")
            if rev:
                log.info("前端缓存已刷新 revision=%d", rev)
    elif args.dry_run:
        log.info("dry-run 完成，未写入数据库")


if __name__ == "__main__":
    main()

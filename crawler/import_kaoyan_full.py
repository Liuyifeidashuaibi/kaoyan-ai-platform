#!/usr/bin/env python3
"""
掌上考研 JSON（syl-schools-full.json）→ Supabase 全量导入

将 crawler/data/kaoyan-cn/ 下的 985/211/双一流院校数据写入：
  universities / majors / scores

用法：
  python import_kaoyan_full.py
  python import_kaoyan_full.py --input data/kaoyan-cn/latest/syl-schools-full.json
  python import_kaoyan_full.py --dry-run --school 武汉大学
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

_here = Path(__file__).parent
sys.path.insert(0, str(_here))
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")
load_dotenv(_here.parent / ".env.local")

from enrich_constants import SCORE_YEARS  # noqa: E402
from import_kaoyan_scores_batch import (  # noqa: E402
    BATCH_SIZE,
    batch_upsert,
    resolve_major_id_relaxed,
)
from notify_frontend import bump_schools_sync  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("import_kaoyan_full")

DEFAULT_INPUT = _here / "data" / "kaoyan-cn" / "syl-schools-full.json"
LATEST_INPUT = _here / "data" / "kaoyan-cn" / "latest" / "syl-schools-full.json"


def _sb() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def _parse_int(val: Any) -> Optional[int]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return int(val)
    m = re.search(r"\d+", str(val))
    return int(m.group()) if m else None


def map_degree(degree_type_name: str = "", degree_type: Any = None) -> str:
    text = (degree_type_name or "").strip()
    if "专" in text or degree_type == 1:
        return "专硕"
    return "学硕"


def map_school_type(type_name: str) -> str:
    t = (type_name or "").strip().replace("类", "")
    return t or "综合"


def pick_website(overview: dict) -> Optional[str]:
    for key in ("school_site", "site"):
        val = overview.get(key)
        if isinstance(val, list) and val:
            return str(val[0]).strip() or None
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def build_university_row(school: dict) -> dict:
    labels = school.get("labels") or []
    overview = school.get("overview") or {}
    province = (school.get("location") or overview.get("province") or "").strip()

    is_985 = "985" in labels or overview.get("is_985") == 1
    is_211 = "211" in labels or overview.get("is_211") == 1
    is_syl = "双一流" in labels or overview.get("is_syl") == 1

    intro = (overview.get("intro") or "").strip()
    if len(intro) > 2000:
        intro = intro[:2000]

    return {
        "name": school["name"].strip(),
        "logo_url": school.get("logo"),
        "province": province,
        "city": province,
        "level_985": is_985,
        "level_211": is_211,
        "double_first_class": "双一流" if is_syl else None,
        "school_type": map_school_type(school.get("type") or overview.get("search_area_name") or ""),
        "intro": intro or None,
        "address": (overview.get("school_address") or "").strip() or None,
        "website": pick_website(overview),
    }


def build_major_rows(university_id: str, school: dict) -> list[dict]:
    plans = school.get("plans") or {}
    items = plans.get("items") or []
    rows: list[dict] = []
    seen: set[tuple] = set()

    for item in items:
        code = re.sub(r"\D", "", str(item.get("special_code") or ""))[:6]
        name = (item.get("special_name") or "").strip()
        if len(code) != 6 or not name:
            continue

        degree = map_degree(item.get("degree_type_name", ""), item.get("degree_type"))
        study_mode = (item.get("recruit_type_name") or "全日制").strip() or "全日制"
        key = (university_id, code, degree, study_mode)
        if key in seen:
            continue
        seen.add(key)

        college = (item.get("depart_name") or "").strip() or "未知学院"
        rows.append({
            "university_id": university_id,
            "college": college[:100],
            "name": name,
            "code": code,
            "degree_type": degree,
            "study_mode": study_mode,
            "exam_type": (item.get("exam_class_name") or "统考").strip() or "统考",
            "enrollment_count": _parse_int(item.get("recruit_number")),
            "subject_category": (item.get("level1_name") or "").strip() or None,
            "first_discipline": (item.get("level2_name") or "").strip() or None,
        })
    return rows


def build_score_rows(
    university_id: str,
    school: dict,
    majors: list[dict],
    allowed_years: set[int],
) -> tuple[list[dict], int]:
    scores = school.get("scores") or {}
    years_data = scores.get("years") or {}
    rows: list[dict] = []
    skipped = 0
    seen: set[tuple] = set()

    for year_str, items in years_data.items():
        year = _parse_int(year_str)
        if not year or year not in allowed_years:
            continue

        for item in items or []:
            if not isinstance(item, dict):
                continue
            if item.get("data_type") and item.get("data_type") != "school_score":
                continue

            total = _parse_int(item.get("total"))
            if not total or total < 140 or total > 510:
                skipped += 1
                continue

            code = (item.get("code") or "").strip()
            name = (item.get("name") or "").strip()
            degree = map_degree(degree_type=item.get("degree_type"))
            college = (item.get("depart_name") or "").strip()

            major_id = resolve_major_id_relaxed(majors, code, name, degree, college)
            if not major_id:
                skipped += 1
                continue

            key = (major_id, year)
            if key in seen:
                continue
            seen.add(key)

            rows.append({
                "university_id": university_id,
                "major_id": major_id,
                "year": year,
                "total_score": total,
                "politics_score": _parse_int(item.get("politics")) or 0,
                "english_score": _parse_int(item.get("english")) or 0,
                "professional1_score": _parse_int(item.get("special_one")),
                "professional2_score": _parse_int(item.get("special_two")),
                "line_diff": _parse_int(item.get("diff_total")),
            })

    return rows, skipped


def load_all_majors(sb: Client) -> dict[str, list[dict]]:
    cache: dict[str, list[dict]] = defaultdict(list)
    offset = 0
    while True:
        res = (
            sb.table("majors")
            .select("id,university_id,code,name,degree_type,study_mode,college,subject_category")
            .range(offset, offset + 999)
            .execute()
        )
        batch = res.data or []
        for m in batch:
            uid = m.get("university_id")
            if uid:
                cache[uid].append(m)
        if len(batch) < 1000:
            break
        offset += 1000
    return dict(cache)


def resolve_input(path_arg: str) -> Path:
    if path_arg:
        return Path(path_arg)
    if LATEST_INPUT.exists():
        return LATEST_INPUT
    return DEFAULT_INPUT


def main() -> None:
    parser = argparse.ArgumentParser(description="掌上考研 JSON 全量导入 Supabase")
    parser.add_argument("--input", default="", help="syl-schools-full.json 路径")
    parser.add_argument("--years", default="2025-2026", help="导入分数年份")
    parser.add_argument("--school", default="", help="仅导入指定学校")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-notify", action="store_true")
    args = parser.parse_args()

    input_path = resolve_input(args.input)
    if not input_path.exists():
        log.error("数据文件不存在: %s", input_path)
        log.error("请先运行: npm run crawler:kaoyan:sync 或复制 syl-schools-full.json")
        sys.exit(1)

    if "-" in args.years:
        a, b = args.years.split("-", 1)
        allowed_years = {y for y in range(int(a), int(b) + 1) if y in SCORE_YEARS}
    else:
        y = int(args.years)
        allowed_years = {y} if y in SCORE_YEARS else set(SCORE_YEARS)

    log.info("读取 %s …", input_path)
    with input_path.open(encoding="utf-8") as f:
        payload = json.load(f)

    schools = payload.get("schools") or []
    if args.school:
        schools = [s for s in schools if s.get("name") == args.school]
        if not schools:
            log.error("未找到学校: %s", args.school)
            sys.exit(1)

    log.info("待导入 %d 所双一流院校，分数年份 %s", len(schools), sorted(allowed_years))

    sb = _sb()
    uni_lookup: dict[str, str] = {}
    all_major_rows: list[dict] = []
    all_score_rows: list[dict] = []
    score_skipped = 0

    for i, school in enumerate(schools, 1):
        name = (school.get("name") or "").strip()
        if not name:
            continue

        uni_row = build_university_row(school)
        if args.dry_run:
            uni_lookup[name] = f"dry-{i}"
            majors = build_major_rows(uni_lookup[name], school)
            all_major_rows.extend(majors)
            score_rows, skipped = build_score_rows(uni_lookup[name], school, majors, allowed_years)
            all_score_rows.extend(score_rows)
            score_skipped += skipped
            continue

        res = sb.table("universities").upsert(uni_row, on_conflict="name").execute()
        uid = (res.data or [{}])[0].get("id")
        if not uid:
            log.warning("院校入库失败: %s", name)
            continue
        uni_lookup[name] = uid

        major_rows = build_major_rows(uid, school)
        if major_rows:
            batch_upsert(sb, "majors", major_rows, "university_id,code,degree_type,study_mode")
            all_major_rows.extend(major_rows)

        if i % 10 == 0:
            log.info("进度 %d/%d — %s", i, len(schools), name)
            time.sleep(0.2)

    if not args.dry_run:
        majors_cache = load_all_majors(sb)
        for school in schools:
            name = (school.get("name") or "").strip()
            uid = uni_lookup.get(name)
            if not uid:
                continue
            majors = majors_cache.get(uid, [])
            score_rows, skipped = build_score_rows(uid, school, majors, allowed_years)
            all_score_rows.extend(score_rows)
            score_skipped += skipped

        if all_score_rows:
            written = batch_upsert(sb, "scores", all_score_rows, "major_id,year")
            log.info("分数入库 %d 条（跳过 %d）", written, score_skipped)
        else:
            log.warning("无分数可入库（跳过 %d）", score_skipped)

        if not args.no_notify:
            rev = bump_schools_sync("import_kaoyan_full")
            if rev:
                log.info("前端缓存已刷新 revision=%d", rev)

    log.info(
        "完成: 院校 %d | 专业 %d | 分数 %d | dry_run=%s",
        len(uni_lookup),
        len(all_major_rows),
        len(all_score_rows),
        args.dry_run,
    )


if __name__ == "__main__":
    main()

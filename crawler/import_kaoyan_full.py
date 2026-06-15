#!/usr/bin/env python3
"""
掌上考研 JSON（syl-schools-full.json）→ Supabase 全量导入

读取 E:\\Kaoyan\\re（clawer 输出）下的 985/211/双一流 JSON，写入：
  universities / majors / scores

用法：
  python import_kaoyan_full.py
  python import_kaoyan_full.py --input E:\\Kaoyan\\re\\latest\\syl-schools-full.json
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

from db_import_utils import batch_upsert, resolve_major_id_relaxed  # noqa: E402
from enrich_constants import CODE_PREFIX_CATEGORY, SCORE_YEARS  # noqa: E402
from notify_frontend import bump_schools_sync  # noqa: E402
from paths import kaoyan_full_json  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("import_kaoyan_full")

DEFAULT_INPUT = kaoyan_full_json()


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


SUBJECT_CATEGORY_NAMES = frozenset(CODE_PREFIX_CATEGORY.values())
ART_MAJOR_CODE_PREFIXES = ("05", "13", "14")


def _is_broad_level_line(item: dict) -> bool:
    if item.get("data_type") == "score_level":
        return True
    prefix = re.sub(r"\D", "", item.get("code") or "")
    name = (item.get("name") or "").strip()
    return len(prefix) <= 4 or name in SUBJECT_CATEGORY_NAMES


def _majors_for_broad_level(
    majors: list[dict],
    item: dict,
    degree: str | None,
) -> list[dict]:
    """门类/4 位代码分数线：向同学科或同关键词专业展开。"""
    name = (item.get("name") or "").strip()
    prefix = re.sub(r"\D", "", item.get("code") or "")
    college = _normalize_college(item.get("depart_name") or "")
    candidates: list[dict] = []

    if name == "艺术学" or prefix.startswith("1301"):
        candidates = [
            m for m in majors
            if (m.get("subject_category") or "").strip() == "艺术学"
            or re.sub(r"\D", "", str(m.get("code") or ""))[:2] in ART_MAJOR_CODE_PREFIXES
        ]
    elif name == "音乐" or prefix.startswith("1352"):
        candidates = [
            m for m in majors
            if "音乐" in (m.get("name") or "")
            or re.sub(r"\D", "", str(m.get("code") or "")).startswith("1352")
            or re.sub(r"\D", "", str(m.get("code") or "")).startswith("0504")
        ]
    elif name in ("舞蹈", "舞蹈学") or prefix.startswith("1353"):
        candidates = [
            m for m in majors
            if "舞蹈" in (m.get("name") or "")
            or re.sub(r"\D", "", str(m.get("code") or "")).startswith("1353")
            or re.sub(r"\D", "", str(m.get("code") or "")).startswith("0504")
        ]
    elif name in ("戏剧", "戏剧与影视", "戏曲") or prefix.startswith(("1354", "1355", "1356")):
        candidates = [
            m for m in majors
            if any(k in (m.get("name") or "") for k in ("戏剧", "影视", "戏曲"))
            or re.sub(r"\D", "", str(m.get("code") or "")).startswith("0504")
            or re.sub(r"\D", "", str(m.get("code") or "")).startswith("1354")
        ]
    elif name == "教育" or prefix.startswith("0451"):
        candidates = [
            m for m in majors
            if "教育" in (m.get("name") or "")
            or re.sub(r"\D", "", str(m.get("code") or "")).startswith("0451")
            or re.sub(r"\D", "", str(m.get("code") or "")).startswith("0401")
        ]
    elif name in SUBJECT_CATEGORY_NAMES:
        candidates = [m for m in majors if (m.get("subject_category") or "").strip() == name]
        if not candidates:
            cat_prefix = next((k for k, v in CODE_PREFIX_CATEGORY.items() if v == name), None)
            if cat_prefix:
                candidates = [
                    m for m in majors
                    if re.sub(r"\D", "", str(m.get("code") or ""))[:2] == cat_prefix
                ]
    elif len(prefix) >= 2:
        candidates = majors_matching_code(majors, item.get("code") or "", None)

    art_relaxed_names = {"艺术学", "音乐", "舞蹈", "戏剧与影视", "戏剧", "戏曲", "教育"}
    if degree and name not in art_relaxed_names:
        deg_filtered = [m for m in candidates if m.get("degree_type") == degree]
        if deg_filtered:
            candidates = deg_filtered

    broad_pool = list(candidates)
    candidates = _filter_by_college(candidates, college)
    if name in art_relaxed_names and len(candidates) <= 2 and len(broad_pool) > len(candidates):
        candidates = broad_pool
    if name not in SUBJECT_CATEGORY_NAMES:
        candidates = _filter_by_name(candidates, name)
    return candidates


def _normalize_college(college: str) -> str:
    college = (college or "").strip()
    return "" if college in ("全校或院系", "") else college


def _filter_by_college(candidates: list[dict], college: str) -> list[dict]:
    college = _normalize_college(college)
    if not college or len(candidates) <= 1:
        return candidates
    filtered = [
        m for m in candidates
        if college in (m.get("college") or "") or (m.get("college") or "") in college
    ]
    return filtered if filtered else candidates


def _filter_by_name(candidates: list[dict], name: str) -> list[dict]:
    if not name or len(candidates) <= 1:
        return candidates
    name = name.strip()
    exact = [m for m in candidates if (m.get("name") or "").strip() == name]
    if exact:
        return exact
    fuzzy = [
        m for m in candidates
        if name in (m.get("name") or "") or (m.get("name") or "") in name
    ]
    return fuzzy if fuzzy else candidates


def majors_matching_code(
    majors: list[dict],
    level_code: str,
    degree: str | None,
) -> list[dict]:
    prefix = re.sub(r"\D", "", level_code)
    if len(prefix) < 2:
        return []
    matched: list[dict] = []
    for m in majors:
        code6 = re.sub(r"\D", "", str(m.get("code") or ""))[:6]
        if len(code6) != 6 or not code6.startswith(prefix):
            continue
        if degree and m.get("degree_type") != degree:
            continue
        matched.append(m)
    return matched


def majors_for_score_item(majors: list[dict], item: dict) -> list[dict]:
    """将 school_score / score_level 条目映射到一条或多条专业记录。"""
    code = (item.get("code") or "").strip()
    name = (item.get("name") or "").strip()
    college = _normalize_college(item.get("depart_name") or "")
    degree = map_degree(degree_type=item.get("degree_type")) if item.get("degree_type") else None
    prefix = re.sub(r"\D", "", code)

    if _is_broad_level_line(item):
        broad = _majors_for_broad_level(majors, item, degree)
        if broad:
            return broad

    if len(prefix) == 6:
        mid = resolve_major_id_relaxed(majors, code, name, degree or "学硕", college)
        if mid:
            return [m for m in majors if m["id"] == mid]
        candidates = [
            m for m in majors
            if re.sub(r"\D", "", str(m.get("code") or ""))[:6] == prefix
        ]
        if degree:
            deg_filtered = [m for m in candidates if m.get("degree_type") == degree]
            if deg_filtered:
                candidates = deg_filtered
        candidates = _filter_by_college(candidates, college)
        candidates = _filter_by_name(candidates, name)
        if candidates:
            return candidates

    if len(prefix) >= 2:
        for deg in ([degree] if degree else []) + [None]:
            candidates = majors_matching_code(majors, code, deg)
            if candidates:
                candidates = _filter_by_college(candidates, college)
                candidates = _filter_by_name(candidates, name)
                return candidates

    if name in SUBJECT_CATEGORY_NAMES:
        candidates = [m for m in majors if (m.get("subject_category") or "").strip() == name]
        if degree:
            deg_filtered = [m for m in candidates if m.get("degree_type") == degree]
            if deg_filtered:
                candidates = deg_filtered
        candidates = _filter_by_college(candidates, college)
        if candidates:
            return candidates

    if len(prefix) >= 2:
        cat = CODE_PREFIX_CATEGORY.get(prefix[:2])
        if cat:
            candidates = [m for m in majors if (m.get("subject_category") or "").strip() == cat]
            if degree:
                deg_filtered = [m for m in candidates if m.get("degree_type") == degree]
                if deg_filtered:
                    candidates = deg_filtered
            candidates = _filter_by_college(candidates, college)
            candidates = _filter_by_name(candidates, name)
            if candidates:
                return candidates

    if name:
        candidates: list[dict] = []
        for m in majors:
            mname = (m.get("name") or "").strip()
            fd = (m.get("first_discipline") or "").strip()
            sc = (m.get("subject_category") or "").strip()
            if name == mname or name in mname or mname in name:
                candidates.append(m)
            elif name in fd or fd in name:
                candidates.append(m)
            elif name in sc:
                candidates.append(m)
        if degree:
            deg_filtered = [m for m in candidates if m.get("degree_type") == degree]
            if deg_filtered:
                candidates = deg_filtered
        candidates = _filter_by_college(candidates, college)
        if candidates:
            return candidates

    mid = resolve_major_id_relaxed(majors, code, name, degree or "学硕", college)
    if mid:
        return [m for m in majors if m["id"] == mid]
    return []


def process_score_items(
    university_id: str,
    majors: list[dict],
    years_data: dict[Any, list[dict]],
    allowed_years: set[int],
) -> tuple[list[dict], int]:
    rows: list[dict] = []
    skipped = 0
    seen: set[tuple] = set()
    covered: dict[int, set[str]] = defaultdict(set)

    def add_row(major_id: str, year: int, item: dict) -> bool:
        key = (major_id, year)
        if key in seen:
            return False
        total = _parse_int(item.get("total"))
        if not total or total < 140 or total > 510:
            return False
        seen.add(key)
        covered[year].add(major_id)
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
        return True

    for year_str, items in years_data.items():
        year = _parse_int(year_str)
        if not year or year not in allowed_years:
            continue

        school_items: list[dict] = []
        level_items: list[dict] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            dtype = item.get("data_type")
            if dtype == "score_level":
                level_items.append(item)
            elif not dtype or dtype == "school_score":
                school_items.append(item)

        for item in school_items:
            total = _parse_int(item.get("total"))
            if not total or total < 140 or total > 510:
                skipped += 1
                continue
            matched = majors_for_score_item(majors, item)
            if not matched:
                skipped += 1
                continue
            added = False
            for m in matched:
                if m["id"] in covered[year]:
                    continue
                if add_row(m["id"], year, item):
                    added = True
            if not added:
                skipped += 1

        level_items.sort(
            key=lambda x: len(re.sub(r"\D", "", str(x.get("code") or ""))),
            reverse=True,
        )
        for item in level_items:
            total = _parse_int(item.get("total"))
            if not total or total < 140 or total > 510:
                skipped += 1
                continue
            matched = majors_for_score_item(majors, item)
            if not matched:
                skipped += 1
                continue
            added = False
            for m in matched:
                if m["id"] in covered[year]:
                    continue
                if add_row(m["id"], year, item):
                    added = True
            if not added:
                skipped += 1

    return rows, skipped


def build_score_rows(
    university_id: str,
    school: dict,
    majors: list[dict],
    allowed_years: set[int],
) -> tuple[list[dict], int]:
    scores = school.get("scores") or {}
    years_data = scores.get("years") or {}
    return process_score_items(university_id, majors, years_data, allowed_years)


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
        log.error("请先在 E:\\Kaoyan\\clawer 运行 sync，或复制 syl-schools-full.json 到 E:\\Kaoyan\\re\\latest\\")
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
            for j, m in enumerate(majors):
                m["id"] = f"dry-{i}-{j}"
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

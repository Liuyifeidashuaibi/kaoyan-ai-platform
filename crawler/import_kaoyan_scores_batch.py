#!/usr/bin/env python3
"""
掌上考研 CSV → Supabase scores 批量导入（比逐条 upsert 快 50x+）
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import create_client

_here = Path(__file__).parent
sys.path.insert(0, str(_here))
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

from enrich_constants import national_line_for_major, SCORE_YEARS  # noqa: E402
from project_universities import fetch_project_universities, project_university_names  # noqa: E402
from import_kaoyan_scores_csv import (  # noqa: E402
    _COLLEGE_RE,
    _parse_int,
    _valid_college,
    resolve_major_id,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("import_scores_batch")

TARGET_SCHOOLS = project_university_names()

BATCH_SIZE = 500


def _sb():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def load_all_majors(sb) -> dict[str, list[dict]]:
    """university_id → majors[]"""
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


def build_uni_lookup(sb) -> dict[str, str]:
    """仅项目内院校：name → university_id。"""
    try:
        return {u["name"]: u["id"] for u in fetch_project_universities()}
    except Exception:
        res = sb.table("universities").select("id,name").execute()
        return {(r.get("name") or "").strip(): r["id"] for r in (res.data or []) if r.get("name")}


def resolve_major_id_relaxed(
    majors: list[dict],
    code: str,
    name: str,
    degree_type: str,
    college: str = "",
) -> Optional[str]:
    """先严格匹配，再按代码/名称兜底；有学院时优先同学院专业。"""
    mid = resolve_major_id(majors, code, name, degree_type)
    if mid:
        return mid

    code6 = re.sub(r"\D", "", code)[:6]
    college = (college or "").strip()

    if len(code6) == 6:
        by_code = [m for m in majors if re.sub(r"\D", "", str(m.get("code") or ""))[:6] == code6]
        if college and by_code:
            by_college = [
                m for m in by_code
                if college in (m.get("college") or "") or (m.get("college") or "") in college
            ]
            if len(by_college) == 1:
                return by_college[0]["id"]
            if by_college:
                by_code = by_college
        if len(by_code) == 1:
            return by_code[0]["id"]
        if by_code:
            return max(
                by_code,
                key=lambda m: (1 if m.get("study_mode") == "全日制" else 0, len(m.get("college") or "")),
            )["id"]

    if name:
        name = name.strip()
        by_name = [m for m in majors if (m.get("name") or "").strip() == name]
        if len(by_name) == 1:
            return by_name[0]["id"]
        for m in majors:
            mname = (m.get("name") or "").strip()
            if mname and (name in mname or mname in name):
                return m["id"]
    return None


def csv_to_score_rows(
    rows: list[dict],
    uni_lookup: dict[str, str],
    majors_cache: dict[str, list[dict]],
) -> tuple[list[dict], list[dict], int]:
    """返回 (score_rows, college_updates, skipped)"""
    score_rows: list[dict] = []
    college_updates: list[dict] = []
    skipped = 0
    seen: set[tuple] = set()

    for row in rows:
        school = (row.get("学校名称") or "").strip()
        uid = uni_lookup.get(school)
        if not uid:
            skipped += 1
            continue

        majors = majors_cache.get(uid, [])
        code = (row.get("专业代码") or "").strip()
        name = (row.get("专业名称") or "").strip()
        degree = (row.get("学位类型") or "学硕").strip() or "学硕"
        year = _parse_int(row.get("年份"))
        total = _parse_int(row.get("总分复试线"))
        if not year or not total or total < 140 or total > 510:
            skipped += 1
            continue

        college = (row.get("学院") or "").strip()
        major_id = resolve_major_id_relaxed(majors, code, name, degree, college)
        if not major_id:
            skipped += 1
            continue

        key = (major_id, year)
        if key in seen:
            continue
        seen.add(key)

        if _valid_college(college):
            major_row = next((m for m in majors if m["id"] == major_id), None)
            if major_row and not _valid_college((major_row.get("college") or "").strip()):
                college_updates.append({"id": major_id, "college": college[:100]})
                major_row["college"] = college

        major_row = next((m for m in majors if m["id"] == major_id), None)
        line_diff = None
        if major_row:
            nl = national_line_for_major(
                code,
                major_row.get("subject_category"),
                major_row.get("degree_type"),
            )
            if nl is not None:
                line_diff = total - nl

        score_rows.append({
            "university_id": uid,
            "major_id": major_id,
            "year": year,
            "total_score": total,
            "politics_score": _parse_int(row.get("政治单科线")) or 0,
            "english_score": _parse_int(row.get("英语单科线")) or 0,
            "professional1_score": _parse_int(row.get("业务课一")),
            "professional2_score": _parse_int(row.get("业务课二")),
            "line_diff": line_diff,
        })

    return score_rows, college_updates, skipped


def batch_upsert(sb, table: str, rows: list[dict], on_conflict: str) -> int:
    written = 0
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i : i + BATCH_SIZE]
        try:
            sb.table(table).upsert(chunk, on_conflict=on_conflict).execute()
            written += len(chunk)
        except Exception as exc:
            log.error("batch upsert %s [%d:%d]: %s", table, i, i + len(chunk), exc)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="批量导入复试线 CSV")
    parser.add_argument("--input", default=str(_here / "data" / "kaoyan_scores_985_211.csv"))
    parser.add_argument("--years", default="2025-2026")
    args = parser.parse_args()

    csv_path = Path(args.input)
    if not csv_path.exists():
        log.error("CSV 不存在: %s", csv_path)
        sys.exit(1)

    if "-" in args.years:
        a, b = args.years.split("-", 1)
        allowed = {y for y in range(int(a), int(b) + 1) if y in SCORE_YEARS}
    else:
        y = int(args.years)
        allowed = {y} if y in SCORE_YEARS else set(SCORE_YEARS)

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    rows = [
        r for r in rows
        if _parse_int(r.get("年份")) in allowed
        and (r.get("学校名称") or "").strip() in TARGET_SCHOOLS
    ]
    log.info("CSV 有效行 %d（985/211/双一流），年份 %s", len(rows), sorted(allowed))

    sb = _sb()
    uni_lookup = build_uni_lookup(sb)
    majors_cache = load_all_majors(sb)
    log.info("院校 %d，专业缓存 %d 校", len(uni_lookup), len(majors_cache))

    score_rows, college_updates, skipped = csv_to_score_rows(rows, uni_lookup, majors_cache)
    log.info("解析完成：可写入 %d，跳过 %d，学院补全 %d", len(score_rows), skipped, len(college_updates))

    scores_written = batch_upsert(sb, "scores", score_rows, "major_id,year")
    colleges_written = 0
    if college_updates:
        deduped = {u["id"]: u for u in college_updates}
        for mid, payload in deduped.items():
            try:
                sb.table("majors").update({"college": payload["college"]}).eq("id", mid).execute()
                colleges_written += 1
            except Exception as exc:
                log.debug("college update %s: %s", mid, exc)

    summary = {
        "csv_rows": len(rows),
        "scores_upserted": scores_written,
        "colleges_updated": colleges_written,
        "skipped": skipped,
    }
    log.info("导入完成: %s", json.dumps(summary, ensure_ascii=False))

    if scores_written > 0:
        from notify_frontend import bump_schools_sync
        bump_schools_sync("import_kaoyan_scores_batch")


if __name__ == "__main__":
    main()

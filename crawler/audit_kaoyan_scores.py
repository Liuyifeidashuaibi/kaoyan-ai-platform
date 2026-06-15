#!/usr/bin/env python3
"""
审计掌上考研分数入库覆盖率

对比 JSON 源数据与 Supabase scores 表，找出分数缺失严重的院校。

用法：
  python audit_kaoyan_scores.py
  python audit_kaoyan_scores.py --school 北京大学
  python audit_kaoyan_scores.py --min-coverage 50

默认读取 E:\\Kaoyan\\re\\latest\\syl-schools-full.json（可用 --input 覆盖）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_here = Path(__file__).parent
sys.path.insert(0, str(_here))
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")
load_dotenv(_here.parent / ".env.local")

from enrich_constants import SCORE_YEARS  # noqa: E402
from import_kaoyan_full import (  # noqa: E402
    build_major_rows,
    build_score_rows,
    load_all_majors,
    map_degree,
    resolve_input,
)

REPORT_PATH = _here / "logs" / "audit_scores_report.json"


def _sb():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def count_db_scores(sb, uni_lookup: dict[str, str], years: set[int]) -> dict[str, dict[int, int]]:
    counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for name, uid in uni_lookup.items():
        for year in years:
            cnt = (
                sb.table("scores")
                .select("id", count="exact")
                .eq("university_id", uid)
                .eq("year", year)
                .limit(0)
                .execute()
                .count
                or 0
            )
            counts[name][year] = cnt
    return counts


def json_score_potential(school: dict, years: set[int]) -> dict[int, dict[str, int]]:
    """统计 JSON 中可导入的分数潜力（专业级 + 门类级展开前）。"""
    result: dict[int, dict[str, int]] = {}
    years_data = (school.get("scores") or {}).get("years") or {}
    for year_str, items in years_data.items():
        year = int(year_str) if str(year_str).isdigit() else None
        if not year or year not in years:
            continue
        school_n = 0
        level_n = 0
        for item in items or []:
            if not isinstance(item, dict):
                continue
            dtype = item.get("data_type")
            if dtype == "score_level":
                level_n += 1
            elif not dtype or dtype == "school_score":
                school_n += 1
        result[year] = {"school_score": school_n, "score_level": level_n}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="分数入库覆盖率审计")
    parser.add_argument("--input", default="")
    parser.add_argument("--school", default="")
    parser.add_argument("--min-coverage", type=int, default=30, help="专业覆盖率低于此值则标记漏洞")
    parser.add_argument("--years", default="2025-2026")
    args = parser.parse_args()

    if "-" in args.years:
        a, b = args.years.split("-", 1)
        years = {y for y in range(int(a), int(b) + 1) if y in SCORE_YEARS}
    else:
        years = set(SCORE_YEARS)

    input_path = resolve_input(args.input)
    with input_path.open(encoding="utf-8") as f:
        payload = json.load(f)

    schools = payload.get("schools") or []
    if args.school:
        schools = [s for s in schools if s.get("name") == args.school]

    sb = _sb()
    uni_rows = sb.table("universities").select("id,name").execute().data or []
    uni_lookup = {r["name"]: r["id"] for r in uni_rows if r.get("name")}
    majors_cache = load_all_majors(sb)
    db_counts = count_db_scores(sb, uni_lookup, years)

    issues: list[dict] = []
    summary_rows: list[dict] = []

    for school in schools:
        name = (school.get("name") or "").strip()
        uid = uni_lookup.get(name)
        if not uid:
            issues.append({"school": name, "issue": "院校未入库"})
            continue

        majors = majors_cache.get(uid, [])
        major_count = len(majors)
        if major_count == 0:
            major_rows = build_major_rows(uid, school)
            major_count = len(major_rows)

        sim_rows, skipped = build_score_rows(uid, school, majors, years)
        sim_by_year: dict[int, int] = defaultdict(int)
        for r in sim_rows:
            sim_by_year[r["year"]] += 1

        json_pot = json_score_potential(school, years)
        db_by_year = db_counts.get(name, {})

        for year in sorted(years):
            db_n = db_by_year.get(year, 0)
            sim_n = sim_by_year.get(year, 0)
            pot = json_pot.get(year, {})
            coverage = round(100 * db_n / major_count, 1) if major_count else 0
            sim_coverage = round(100 * sim_n / major_count, 1) if major_count else 0

            row = {
                "school": name,
                "year": year,
                "majors": major_count,
                "db_scores": db_n,
                "importable_scores": sim_n,
                "json_school_score": pot.get("school_score", 0),
                "json_score_level": pot.get("score_level", 0),
                "db_coverage_pct": coverage,
                "importable_coverage_pct": sim_coverage,
                "skipped": skipped,
            }
            summary_rows.append(row)

            if sim_coverage < args.min_coverage and pot.get("school_score", 0) + pot.get("score_level", 0) > 0:
                issues.append({
                    **row,
                    "issue": "分数覆盖不足",
                })
            elif db_n < sim_n * 0.9 and sim_n > 0:
                issues.append({
                    **row,
                    "issue": "数据库分数少于可导入量，需重新导入",
                })

    issues.sort(key=lambda x: (x.get("importable_coverage_pct", 0), x.get("db_coverage_pct", 0)))

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps({"years": sorted(years), "issues": issues, "summary": summary_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n审计完成（{len(schools)} 校，年份 {sorted(years)}）")
    print(f"报告: {REPORT_PATH}\n")

    flagged = [i for i in issues if i.get("issue")]
    print(f"发现 {len(flagged)} 条问题记录（覆盖率 < {args.min_coverage}% 或需重导）:\n")
    for item in flagged[:40]:
        print(
            f"  [{item.get('issue')}] {item['school']} {item['year']}年 | "
            f"专业{item['majors']} | DB{item['db_scores']} | 可导入{item['importable_scores']} | "
            f"JSON专{item.get('json_school_score',0)}+门{item.get('json_score_level',0)} | "
            f"覆盖{item.get('importable_coverage_pct',0)}%"
        )
    if len(flagged) > 40:
        print(f"  ... 另有 {len(flagged) - 40} 条，见报告文件")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
掌上考研 CSV → Supabase scores 导入
============================================================
将 crawl_kaoyan_scores_csv.py 导出的 CSV 写入 scores 表，并补全 majors.college。

用法：
  python import_kaoyan_scores_csv.py --input data/kaoyan_scores_985_211.csv
  python import_kaoyan_scores_csv.py --crawl --school 武汉大学 --limit 2
  python import_kaoyan_scores_csv.py --dry-run --input data/kaoyan_scores_985_211.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

from crawl_updates_smart import DB, upsert_score_from_item  # noqa: E402
from enrich_constants import national_line_for_major, SCORE_YEARS  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("import_scores")

_COLLEGE_RE = re.compile(r"学院|系|中心|部|研究所|研究院|实验室")


def _sb() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def _parse_int(val: Any) -> Optional[int]:
    if val is None or val == "":
        return None
    m = re.search(r"\d+", str(val))
    return int(m.group()) if m else None


def build_uni_lookup(sb: Client) -> dict[str, str]:
    res = sb.table("universities").select("id,name").execute()
    lookup: dict[str, str] = {}
    for row in res.data or []:
        name = (row.get("name") or "").strip()
        if name:
            lookup[name] = row["id"]
    return lookup


def get_majors_for_uni(sb: Client, university_id: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        res = (
            sb.table("majors")
            .select("id,code,name,degree_type,study_mode,college,subject_category")
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


def resolve_major_id(
    majors: list[dict],
    code: str,
    name: str,
    degree_type: str,
) -> Optional[str]:
    """按代码+学位匹配 major_id，同名/包含名兜底。"""
    code6 = re.sub(r"\D", "", code)[:6]
    if len(code6) != 6:
        code6 = ""

    candidates = []
    for m in majors:
        mcode = re.sub(r"\D", "", str(m.get("code") or ""))[:6]
        if code6 and mcode != code6:
            continue
        if degree_type and m.get("degree_type") and m["degree_type"] != degree_type:
            continue
        candidates.append(m)

    if not candidates and code6:
        candidates = [m for m in majors if re.sub(r"\D", "", str(m.get("code") or ""))[:6] == code6]

    if not candidates and name:
        for m in majors:
            mname = (m.get("name") or "").strip()
            if mname == name or (name in mname or mname in name):
                candidates.append(m)

    if not candidates:
        return None

    def score(m: dict) -> tuple[int, int]:
        sm = 1 if m.get("study_mode") == "全日制" else 0
        college_len = len((m.get("college") or "").strip())
        return (sm, college_len)

    best = max(candidates, key=score)
    return best["id"]


def _valid_college(college: str) -> bool:
    c = (college or "").strip()
    return bool(c and c != "未知学院" and _COLLEGE_RE.search(c))


def import_row(
    db: DB,
    sb: Client,
    uni_lookup: dict[str, str],
    majors_cache: dict[str, list[dict]],
    row: dict,
    *,
    dry_run: bool,
) -> tuple[bool, bool]:
    """返回 (score_written, college_updated)。"""
    school = (row.get("学校名称") or "").strip()
    uid = uni_lookup.get(school)
    if not uid:
        log.debug("未匹配院校: %s", school)
        return False, False

    if uid not in majors_cache:
        majors_cache[uid] = get_majors_for_uni(sb, uid)
    majors = majors_cache[uid]

    code = (row.get("专业代码") or "").strip()
    name = (row.get("专业名称") or "").strip()
    degree = (row.get("学位类型") or "学硕").strip() or "学硕"
    year = _parse_int(row.get("年份"))
    total = _parse_int(row.get("总分复试线"))
    if not year or not total:
        return False, False

    major_id = resolve_major_id(majors, code, name, degree)
    college_updated = False
    college = (row.get("学院") or "").strip()

    if major_id and _valid_college(college):
        for m in majors:
            if m["id"] == major_id:
                existing = (m.get("college") or "").strip()
                if not _valid_college(existing):
                    if not dry_run:
                        sb.table("majors").update({"college": college[:100]}).eq("id", major_id).execute()
                    m["college"] = college
                    college_updated = True
                break

    if not major_id:
        log.debug("[%s] 未匹配专业 %s %s %s", school, code, name, degree)
        return False, college_updated

    item = {
        "major_code": code,
        "major_name": name,
        "college": college,
        "total_score": total,
        "politics_score": _parse_int(row.get("政治单科线")),
        "english_score": _parse_int(row.get("英语单科线")),
        "professional1_score": _parse_int(row.get("业务课一")),
        "professional2_score": _parse_int(row.get("业务课二")),
        "type": "复试分数线",
    }

    major_map = {
        re.sub(r"\D", "", str(m.get("code") or ""))[:6]: m["id"]
        for m in majors
        if m.get("code")
    }
    name_map = {(m.get("name") or "").strip(): m["id"] for m in majors if m.get("name")}

    if dry_run:
        return True, college_updated

    written = upsert_score_from_item(db, uid, item, year, major_map, name_map)

    if written:
        major_row = next((m for m in majors if m["id"] == major_id), None)
        if major_row and major_row.get("line_diff") is None:
            nl = national_line_for_major(
                code,
                major_row.get("subject_category"),
                major_row.get("degree_type"),
            )
            if nl is not None:
                sb.table("scores").update({"line_diff": total - nl}).eq("major_id", major_id).eq("year", year).execute()

    return written, college_updated


def read_csv_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    return list(reader)


def run_crawl(args: argparse.Namespace) -> Path:
    cmd = [
        sys.executable,
        str(_here / "crawl_kaoyan_scores_csv.py"),
        "--output",
        args.input,
        "--years",
        args.years,
    ]
    if args.school:
        cmd.extend(["--school", args.school])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    if args.no_chsi:
        cmd.append("--no-chsi")
    import os
    if os.environ.get("CRAWLER_FAST"):
        cmd.extend(["--concurrency", "8"])
    log.info("抓取 CSV: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(_here))
    return Path(args.input)


def _parse_years_arg(years_arg: str) -> set[int]:
    years_arg = (years_arg or "").strip()
    if "-" in years_arg:
        a, b = years_arg.split("-", 1)
        lo, hi = int(a), int(b)
        return {y for y in range(lo, hi + 1) if y in SCORE_YEARS}
    y = int(years_arg)
    return {y} if y in SCORE_YEARS else set(SCORE_YEARS)


def main() -> None:
    parser = argparse.ArgumentParser(description="掌上考研 CSV 导入 Supabase scores")
    parser.add_argument("--input", default=str(_here / "data" / "kaoyan_scores_985_211.csv"))
    parser.add_argument("--crawl", action="store_true", help="先抓取 CSV 再导入")
    parser.add_argument("--school", default=None, help="仅处理指定院校（配合 --crawl）")
    parser.add_argument("--limit", type=int, default=0, help="抓取院校数上限")
    parser.add_argument("--years", default="2025-2026", help="抓取年份范围")
    parser.add_argument("--no-chsi", action="store_true", help="抓取时不访问研招网")
    parser.add_argument("--dry-run", action="store_true", help="仅统计不写库")
    args = parser.parse_args()

    csv_path = Path(args.input)
    if args.crawl:
        csv_path = run_crawl(args)

    if not csv_path.exists():
        log.error("CSV 不存在: %s", csv_path)
        sys.exit(1)

    rows = read_csv_rows(csv_path)
    if not rows:
        log.warning("CSV 无数据")
        return

    allowed_years = _parse_years_arg(args.years)
    rows = [r for r in rows if _parse_int(r.get("年份")) in allowed_years]
    log.info("仅导入年份 %s，有效行 %d", sorted(allowed_years), len(rows))

    sb = _sb()
    db = DB()
    uni_lookup = build_uni_lookup(sb)
    majors_cache: dict[str, list[dict]] = {}

    scores_written = 0
    colleges_updated = 0
    skipped = 0

    for row in rows:
        try:
            written, college_up = import_row(
                db, sb, uni_lookup, majors_cache, row, dry_run=args.dry_run
            )
            if written:
                scores_written += 1
            else:
                skipped += 1
            if college_up:
                colleges_updated += 1
        except Exception as exc:
            log.error("行导入失败 %s: %s", row.get("学校名称"), exc)
            skipped += 1

    summary = {
        "csv_rows": len(rows),
        "scores_upserted": scores_written,
        "colleges_updated": colleges_updated,
        "skipped": skipped,
        "dry_run": args.dry_run,
    }
    log.info("导入完成: %s", json.dumps(summary, ensure_ascii=False))

    if not args.dry_run and scores_written > 0:
        from notify_frontend import bump_schools_sync

        bump_schools_sync("import_kaoyan_scores")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
2025/2026 复试线爬虫（985/211/双一流 · 串行 · CSV + SQLite）
============================================================
数据源：掌上考研 H5 API（首选）→ zhijiao HTML 表格（兜底）
排除：国家线、校线（score_level），仅保留 school_score

用法：
  python crawl_retest_scores.py --limit 3
  python crawl_retest_scores.py --school 华东师范大学
  python crawl_retest_scores.py --offset 50
"""
from __future__ import annotations

import argparse
import csv
import logging
import re
import sqlite3
import sys
from pathlib import Path

import requests

_here = Path(__file__).parent
sys.path.insert(0, str(_here))

from kaoyan_score_sources import (
    fetch_school_score_h5,
    fetch_school_score_pages,
    load_school_id_cache,
    polite_sleep,
    resolve_school_id,
    save_school_id_cache,
)
from crawl_basic_once import UNIVERSITIES

(_here / "logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_here / "logs" / "retest_scores.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("retest_scores")

YEARS = (2025, 2026)
CSV_FIELDS = [
    "年份",
    "院校名称",
    "学院",
    "专业名称",
    "学硕/专硕",
    "总分线",
    "政治线",
    "英语线",
    "业务课1线",
    "业务课2线",
    "数据来源",
]
_NATIONAL_KW = re.compile(r"国家\s*[AＡ]?\s*区?线|执行国家线|国家线")
_DEFAULT_CSV = _here / "data" / "retest_scores_2025_2026.csv"
_DEFAULT_DB = _here / "data" / "retest_scores.db"


def _fmt_score(val) -> str:
    if val is None or val == "":
        return "无"
    try:
        return str(int(val))
    except (TypeError, ValueError):
        s = str(val).strip()
        return s if s else "无"


def _fmt_college(val: str) -> str:
    s = (val or "").strip()
    if not s or s in ("全校或院系", "-", "—"):
        return "无"
    return s


def item_to_record(university: str, item: dict) -> dict | None:
    if item.get("data_type") and item["data_type"] != "school_score":
        return None
    name = (item.get("major_name") or "").strip()
    if not name or _NATIONAL_KW.search(name):
        return None
    total = item.get("total_score")
    if total is None:
        return None

    return {
        "年份": item.get("year"),
        "院校名称": university,
        "学院": _fmt_college(item.get("college", "")),
        "专业名称": name,
        "学硕/专硕": item.get("degree_type") or "无",
        "总分线": _fmt_score(total),
        "政治线": _fmt_score(item.get("politics_score")),
        "英语线": _fmt_score(item.get("english_score")),
        "业务课1线": _fmt_score(item.get("professional1_score")),
        "业务课2线": _fmt_score(item.get("professional2_score")),
        "数据来源": item.get("source", "kaoyan"),
    }


def fetch_school_rows(session: requests.Session, school_id: int, year: int) -> list[dict]:
    rows = fetch_school_score_h5(session, school_id, year)
    professional = [r for r in rows if r.get("data_type") == "school_score"]
    if professional:
        return professional

    fallback: list[dict] = []
    for degree_type, degree_label in ((2, "学硕"), (1, "专硕")):
        html_rows = fetch_school_score_pages(
            session, school_id, year,
            degree_type=degree_type,
            degree_label=degree_label,
        )
        for r in html_rows:
            r["data_type"] = "school_score"
            r["source"] = "kaoyan_html"
        fallback.extend(html_rows)
    return fallback


def dedupe_records(records: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for r in records:
        key = (
            r["年份"],
            r["院校名称"],
            r["学院"],
            r["专业名称"],
            r["学硕/专硕"],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def write_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS retest_scores (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            year          INTEGER NOT NULL,
            university    TEXT    NOT NULL,
            college       TEXT    NOT NULL DEFAULT '无',
            major_name    TEXT    NOT NULL,
            degree_type   TEXT    NOT NULL,
            total_score   TEXT    NOT NULL DEFAULT '无',
            politics      TEXT    NOT NULL DEFAULT '无',
            english       TEXT    NOT NULL DEFAULT '无',
            pro1          TEXT    NOT NULL DEFAULT '无',
            pro2          TEXT    NOT NULL DEFAULT '无',
            source        TEXT,
            created_at    TEXT    DEFAULT (datetime('now','localtime')),
            UNIQUE (year, university, college, major_name, degree_type)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_retest_univ_year
        ON retest_scores (university, year)
    """)
    conn.commit()


def write_sqlite(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        init_db(conn)
        for r in records:
            conn.execute(
                """
                INSERT OR REPLACE INTO retest_scores
                    (year, university, college, major_name, degree_type,
                     total_score, politics, english, pro1, pro2, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r["年份"],
                    r["院校名称"],
                    r["学院"],
                    r["专业名称"],
                    r["学硕/专硕"],
                    r["总分线"],
                    r["政治线"],
                    r["英语线"],
                    r["业务课1线"],
                    r["业务课2线"],
                    r["数据来源"],
                ),
            )
        conn.commit()
    finally:
        conn.close()


def target_schools(school_arg: str | None, limit: int, offset: int) -> list[str]:
    """仅返回项目 universities 表内校名。"""
    try:
        names = [u["name"] for u in fetch_project_universities()]
    except Exception:
        from crawl_basic_once import UNIVERSITIES
        names = [u["name"] for u in UNIVERSITIES]
    if school_arg:
        names = [n for n in names if school_arg in n]
    if offset > 0:
        names = names[offset:]
    if limit > 0:
        names = names[:limit]
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description="2025/2026 复试线爬虫（985/211/双一流）")
    parser.add_argument("--school", default=None, help="校名模糊匹配")
    parser.add_argument("--limit", type=int, default=0, help="最多 N 校（0=全部 148 所）")
    parser.add_argument("--offset", type=int, default=0, help="跳过前 N 校")
    parser.add_argument("--csv", default=str(_DEFAULT_CSV))
    parser.add_argument("--db", default=str(_DEFAULT_DB))
    args = parser.parse_args()

    schools = target_schools(args.school, args.limit, args.offset)
    if not schools:
        log.error("无匹配院校（范围：项目内院校）")
        sys.exit(1)

    session = requests.Session()
    id_cache = load_school_id_cache()
    all_records: list[dict] = []

    log.info("开始 | 项目院校 %d 所 | 年份 %s | 模式=串行", len(schools), list(YEARS))

    for i, name in enumerate(schools, 1):
        sid = resolve_school_id(session, name, id_cache)
        if not sid:
            log.warning("(%d/%d) %s 未找到 school_id，跳过", i, len(schools), name)
            continue
        save_school_id_cache(id_cache)
        school_records: list[dict] = []
        try:
            for year in YEARS:
                year_rows: list[dict] = []
                raw = fetch_school_rows(session, sid, year)
                for item in raw:
                    rec = item_to_record(name, item)
                    if rec:
                        year_rows.append(rec)
                school_records.extend(year_rows)
                log.info(
                    "(%d/%d) %s %d年 → %d 条",
                    i, len(schools), name, year, len(year_rows),
                )
            all_records.extend(school_records)
        except Exception as exc:
            log.error("(%d/%d) %s 失败: %s", i, len(schools), name, exc)
        polite_sleep(2.0, 3.0)

    all_records = dedupe_records(all_records)
    csv_path = Path(args.csv)
    db_path = Path(args.db)
    write_csv(all_records, csv_path)
    write_sqlite(all_records, db_path)

    log.info("完成 | 共 %d 条 | CSV=%s | DB=%s", len(all_records), csv_path, db_path)


if __name__ == "__main__":
    main()

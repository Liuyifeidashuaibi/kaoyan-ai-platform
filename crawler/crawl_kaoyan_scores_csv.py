#!/usr/bin/env python3
"""
掌上考研 + 研招网 复试分数线 CSV 导出
============================================================
优先抓取 zhijiao.cn（掌上考研网页版）院校分数线，研招网专业目录用于核对学院/专业代码。

用法：
  python crawl_kaoyan_scores_csv.py --limit 5          # 试跑 5 所
  python crawl_kaoyan_scores_csv.py --school 武汉大学
  python crawl_kaoyan_scores_csv.py --years 2021-2025
  python crawl_kaoyan_scores_csv.py --output data/kaoyan_scores.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests

_here = Path(__file__).parent
sys.path.insert(0, str(_here))

from crawl_basic_once import UNIVERSITIES
from project_universities import fetch_project_universities
from kaoyan_score_sources import (
    USER_AGENTS,
    fetch_html,
    fetch_school_major_index,
    fetch_school_score_h5,
    fetch_school_score_pages,
    load_school_id_cache,
    match_major_meta,
    norm_name,
    polite_sleep,
    resolve_school_id,
    save_school_id_cache,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("kaoyan_csv")

SCHOOL_CODES_PATH = _here / "data" / "school_codes.json"
CHSI_ZSML = "https://yz.chsi.com.cn/zsml"
YEARS_DEFAULT = [2025, 2026]

CSV_FIELDS = [
    "学校名称",
    "是否985",
    "是否211",
    "是否双一流",
    "学院",
    "专业代码",
    "专业名称",
    "年份",
    "学位类型",
    "政治单科线",
    "英语单科线",
    "业务课一",
    "业务课二",
    "业务课线",
    "总分复试线",
    "数据来源",
]


def load_school_codes() -> dict[str, str]:
    try:
        data = json.loads(SCHOOL_CODES_PATH.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()}
    except Exception as exc:
        log.warning("无法加载 school_codes.json: %s", exc)
        return {}


def target_universities(only_school: Optional[str]) -> list[dict]:
    """仅抓取项目 universities 表内院校。"""
    try:
        schools = fetch_project_universities()
    except Exception as exc:
        log.warning("无法读取 Supabase 院校，回退 UNIVERSITIES 种子: %s", exc)
        schools = [
            {**u, "id": None, "school_code": ""}
            for u in UNIVERSITIES
        ]
    if only_school:
        schools = [u for u in schools if only_school in u.get("name", "")]
    return schools


def _chsi_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": f"{CHSI_ZSML}/",
        "Accept": "application/json, text/plain, */*",
    }


def fetch_chsi_major_index(
    session: requests.Session,
    school_name: str,
    dwdm: str,
) -> list[dict]:
    """研招网专业目录：学院 + 专业代码 + 专业名称（用于核对补全）。"""
    if not dwdm:
        return []

    session.get(f"{CHSI_ZSML}/", headers=_chsi_headers(), timeout=20)
    polite_sleep(2, 4)

    majors: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for mldm in [f"{i:02d}" for i in range(1, 15)]:
        start = 0
        while True:
            params = {
                "dwdm": dwdm,
                "dwmc": school_name,
                "mldm": mldm,
                "xxfs": "1",
                "start": str(start),
            }
            polite_sleep(2, 4)
            try:
                resp = session.get(
                    f"{CHSI_ZSML}/rs/zys.do",
                    params=params,
                    headers=_chsi_headers(),
                    timeout=30,
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                msg = data.get("msg")
                if isinstance(msg, str):
                    if "频繁" in msg:
                        time.sleep(5)
                        continue
                    break
                if not isinstance(msg, dict):
                    break
                items = msg.get("list") or []
                if not items:
                    break
                for item in items:
                    code = re.sub(r"\D", "", str(item.get("zydm", "")))[:6]
                    name = str(item.get("zymc", "")).strip()
                    college = str(item.get("yxsmc") or item.get("xymc") or "").strip()
                    if len(code) != 6 or not name:
                        continue
                    key = (code, name)
                    if key in seen:
                        continue
                    seen.add(key)
                    majors.append({
                        "major_code": code,
                        "major_name": name,
                        "college": college[:80],
                    })
                if len(items) < 20:
                    break
                start += len(items)
            except Exception as exc:
                log.debug("chsi %s mldm=%s: %s", school_name, mldm, exc)
                break
    return majors


def enrich_with_majors(row: dict, kaoyan_majors: list[dict], chsi_majors: list[dict]) -> dict:
    college = row.get("学院", "")
    code = row.get("专业代码", "")
    name = row.get("专业名称", "")

    meta = match_major_meta(name, kaoyan_majors)
    if meta:
        college = college or meta.get("college", "")
        code = code or meta.get("major_code", "")

    if not code or not college:
        chsi_meta = match_major_meta(name, chsi_majors)
        if chsi_meta:
            college = college or chsi_meta.get("college", "")
            code = code or chsi_meta.get("major_code", "")
            if chsi_meta.get("major_name"):
                row["数据来源"] = "kaoyan+chsi"

    row["学院"] = college
    row["专业代码"] = code
    return row


def dedupe_rows(rows: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for r in rows:
        key = (
            r.get("学校名称"),
            r.get("年份"),
            r.get("学位类型"),
            r.get("专业代码") or r.get("专业名称"),
            r.get("学院"),
            r.get("总分复试线"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def row_to_csv_dict(
    uni: dict,
    item: dict,
    *,
    source: str = "kaoyan",
) -> dict:
    p1 = item.get("professional1_score")
    p2 = item.get("professional2_score")
    biz = ""
    if p1 is not None and p2 is not None:
        biz = f"{p1}/{p2}"
    elif p1 is not None:
        biz = str(p1)
    elif p2 is not None:
        biz = str(p2)

    dfc = uni.get("double_first_class")
    return {
        "学校名称": uni["name"],
        "是否985": "是" if uni.get("level_985") else "否",
        "是否211": "是" if uni.get("level_211") else "否",
        "是否双一流": "是" if dfc else "否",
        "学院": item.get("college", ""),
        "专业代码": item.get("major_code", ""),
        "专业名称": item.get("major_name", ""),
        "年份": item.get("year"),
        "学位类型": item.get("degree_type", ""),
        "政治单科线": item.get("politics_score") if item.get("politics_score") is not None else "",
        "英语单科线": item.get("english_score") if item.get("english_score") is not None else "",
        "业务课一": p1 if p1 is not None else "",
        "业务课二": p2 if p2 is not None else "",
        "业务课线": biz,
        "总分复试线": item.get("total_score") if item.get("total_score") is not None else "",
        "数据来源": source,
    }


def crawl_school(
    session: requests.Session,
    uni: dict,
    years: list[int],
    school_id_cache: dict[str, int],
    school_codes: dict[str, str],
    *,
    use_chsi: bool = True,
) -> list[dict]:
    name = uni["name"]
    sid = resolve_school_id(session, name, school_id_cache)
    if not sid:
        log.warning("[%s] 未找到掌上考研 school_id，跳过", name)
        return []

    log.info("[%s] kaoyan school_id=%d", name, sid)

    kaoyan_majors = fetch_school_major_index(session, sid)
    log.info("[%s] 院系专业索引 %d 条", name, len(kaoyan_majors))

    chsi_majors: list[dict] = []
    if use_chsi:
        dwdm = school_codes.get(name, "")
        if dwdm:
            chsi_majors = fetch_chsi_major_index(session, name, dwdm)
            log.info("[%s] 研招网专业索引 %d 条", name, len(chsi_majors))

    raw_items: list[dict] = []
    for year in years:
        h5_rows = fetch_school_score_h5(session, sid, year)
        if h5_rows:
            log.info("[%s] %d年 掌上考研API 复试线 %d 条", name, year, len(h5_rows))
            raw_items.extend(h5_rows)
            continue
        for degree_type, degree_label in ((2, "学硕"), (1, "专硕")):
            rows = fetch_school_score_pages(
                session, sid, year, degree_type=degree_type, degree_label=degree_label,
            )
            if rows:
                log.info("[%s] %d年 %s 网页复试线 %d 条", name, year, degree_label, len(rows))
            raw_items.extend(rows)

    csv_rows: list[dict] = []
    for item in raw_items:
        meta = match_major_meta(item["major_name"], kaoyan_majors) or {}
        merged = {
            **item,
            "college": item.get("college") or meta.get("college", ""),
            "major_code": item.get("major_code") or meta.get("major_code", ""),
        }
        row = row_to_csv_dict(uni, merged, source=item.get("source", "kaoyan"))
        row = enrich_with_majors(row, kaoyan_majors, chsi_majors)
        if row.get("总分复试线") == "" and row.get("政治单科线") == "":
            continue
        csv_rows.append(row)

    return csv_rows


def rows_to_csv_text(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="掌上考研+研招网复试分数线 CSV 导出")
    parser.add_argument("--school", default=None, help="模糊匹配校名")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 所（0=全部 985/211/双一流）")
    parser.add_argument("--years", default="2025-2026", help="年份范围，如 2025-2026 或 2025")
    parser.add_argument("--output", default=str(_here / "data" / "kaoyan_scores_985_211.csv"))
    parser.add_argument("--no-chsi", action="store_true", help="不访问研招网核对")
    parser.add_argument("--refresh-ids", action="store_true", help="强制重新扫描 school_id")
    parser.add_argument("--concurrency", type=int, default=0, help="并行院校数（fast 模式默认 6）")
    parser.add_argument("--offset", type=int, default=0, help="跳过前 N 所院校（断点续跑）")
    args = parser.parse_args()

    if "-" in args.years:
        a, b = args.years.split("-", 1)
        years = list(range(int(a), int(b) + 1))
    else:
        years = [int(args.years)]

    schools = target_universities(args.school)
    if args.offset > 0:
        schools = schools[args.offset :]
    if args.limit > 0:
        schools = schools[: args.limit]
    if not schools:
        log.error("无匹配院校")
        sys.exit(1)

    school_codes = load_school_codes()
    id_cache = {} if args.refresh_ids else load_school_id_cache()
    cache_lock = threading.Lock()

    concurrency = args.concurrency
    if concurrency <= 0:
        import os
        concurrency = 6 if os.environ.get("CRAWLER_FAST") else 1

    all_rows: list[dict] = []
    rows_lock = threading.Lock()

    def _crawl_one(uni: dict) -> list[dict]:
        session = requests.Session()
        with cache_lock:
            local_cache = dict(id_cache)
        try:
            return crawl_school(
                session,
                uni,
                years,
                local_cache,
                school_codes,
                use_chsi=not args.no_chsi,
            )
        finally:
            with cache_lock:
                id_cache.update(local_cache)
                save_school_id_cache(id_cache)

    log.info(
        "开始抓取 | 院校 %d 所 | 年份 %s | chsi=%s | 并发=%d | offset=%d",
        len(schools), years, not args.no_chsi, concurrency, args.offset,
    )

    if concurrency <= 1:
        for i, uni in enumerate(schools, 1):
            log.info("(%d/%d) %s", i, len(schools), uni["name"])
            try:
                rows = _crawl_one(uni)
                all_rows.extend(rows)
            except Exception as exc:
                log.error("[%s] 失败: %s", uni["name"], exc)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(_crawl_one, uni): uni for uni in schools}
            done = 0
            for fut in as_completed(futures):
                uni = futures[fut]
                done += 1
                try:
                    rows = fut.result()
                    with rows_lock:
                        all_rows.extend(rows)
                    log.info("(%d/%d) %s → %d 条", done, len(schools), uni["name"], len(rows))
                except Exception as exc:
                    log.error("[%s] 失败: %s", uni["name"], exc)

    all_rows = dedupe_rows(all_rows)
    csv_text = rows_to_csv_text(all_rows)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(csv_text, encoding="utf-8-sig")

    log.info("完成 | 共 %d 条 | 已写入 %s", len(all_rows), out_path)

    # 同时打印 CSV 供直接复制（大文件只打印摘要）
    if len(all_rows) <= 500:
        print(csv_text)
    else:
        print(rows_to_csv_text(all_rows[:20]))
        print(f"... 共 {len(all_rows)} 行，完整 CSV 见 {out_path}")


if __name__ == "__main__":
    main()

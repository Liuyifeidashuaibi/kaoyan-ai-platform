#!/usr/bin/env python3
"""
多源 + AI 补全专业数据
============================================================
数据源（不只研招网）：
  1. 研啊考研 kaoyana.com — 按专业代码聚合开设院校列表
  2. 各校研究生院 / 招生简章 — Jina Reader + 通义千问提取（复用 crawl_basic_once）
  3. 正则兜底 — 从已抓取页面提取 6 位专业代码

用法：
  python enrich_majors_ai.py --popular          # 热门专硕（人工智能等）从聚合站导入
  python enrich_majors_ai.py --code 085410      # 指定专业代码
  python enrich_majors_ai.py --school 清华大学  # AI 深挖单校官网
  python enrich_majors_ai.py --thin            # 专业数≤95 的院校全部 AI 补采
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import aiohttp
from aiohttp import ClientSession, TCPConnector
from dotenv import load_dotenv

_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

from crawl_basic_once import (  # noqa: E402
    DB,
    collect_majors,
    fetch_page,
    is_likely_major_code,
    is_valid_major_name,
    majors_to_rows,
    normalize_major_code,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("enrich")

# 热门专业：从公开聚合站按代码批量导入开设院校
POPULAR_MAJORS = [
    {
        "code": "085410",
        "name": "人工智能",
        "degree_type": "专硕",
        "subject_category": "工学",
        "first_discipline": "电子信息",
    },
    {
        "code": "085404",
        "name": "计算机技术",
        "degree_type": "专硕",
        "subject_category": "工学",
        "first_discipline": "电子信息",
    },
    {
        "code": "085400",
        "name": "电子信息",
        "degree_type": "专硕",
        "subject_category": "工学",
        "first_discipline": "电子信息",
    },
    {
        "code": "025100",
        "name": "工商管理",
        "degree_type": "专硕",
        "subject_category": "管理学",
        "first_discipline": "工商管理",
    },
    {
        "code": "035101",
        "name": "法律（非法学）",
        "degree_type": "专硕",
        "subject_category": "法学",
        "first_discipline": "法律",
    },
    {
        "code": "045100",
        "name": "教育",
        "degree_type": "专硕",
        "subject_category": "教育学",
        "first_discipline": "教育",
    },
    {
        "code": "081200",
        "name": "计算机科学与技术",
        "degree_type": "学硕",
        "subject_category": "工学",
        "first_discipline": "计算机科学与技术",
    },
    {
        "code": "083500",
        "name": "软件工程",
        "degree_type": "学硕",
        "subject_category": "工学",
        "first_discipline": "软件工程",
    },
]

# 校名别名（聚合站简称 → 库内全称）
NAME_ALIASES: dict[str, str] = {
    "中国矿业大学": "中国矿业大学",
    "中国石油大学（北京）": "中国石油大学（北京）",
    "中国石油大学（华东）": "中国石油大学（华东）",
    "中国地质大学（北京）": "中国地质大学（北京）",
    "中国地质大学（武汉）": "中国地质大学（武汉）",
}


def _normalize_name(name: str) -> str:
    n = (name or "").strip()
    n = re.sub(r"\s+", "", n)
    return n


def _strip_paren(name: str) -> str:
    return re.sub(r"[（(].*?[）)]", "", name).strip()


def build_uni_lookup(db: DB) -> tuple[dict[str, str], dict[str, str]]:
    """归一化校名 → university_id；精确校名 → university_id"""
    res = db._sb.table("universities").select("id,name").execute()
    lookup: dict[str, str] = {}
    exact: dict[str, str] = {}
    for row in res.data or []:
        uid = row["id"]
        name = row["name"]
        exact[name] = uid
        for key in (_normalize_name(name), _normalize_name(_strip_paren(name))):
            lookup[key] = uid
    return lookup, exact


def resolve_university_id(
    school_name: str,
    lookup: dict[str, str],
    exact: dict[str, str],
) -> Optional[str]:
    raw = school_name.strip()
    if raw in NAME_ALIASES:
        raw = NAME_ALIASES[raw]
    if raw in exact:
        return exact[raw]
    for candidate in (
        _normalize_name(raw),
        _normalize_name(_strip_paren(raw)),
    ):
        if candidate in lookup:
            return lookup[candidate]
    return None


def dedupe_major_rows(rows: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str, str], dict] = {}
    for r in rows:
        key = (r["university_id"], r["code"], r["degree_type"], r["study_mode"])
        prev = merged.get(key)
        if not prev or len(r.get("college", "")) > len(prev.get("college", "")):
            merged[key] = r
    return list(merged.values())


def _parse_kaoyana_html(html: str, skip_titles: set[str]) -> list[str]:
    """从研啊考研 HTML 的 h3 标签提取院校名"""
    names: list[str] = []
    for name in re.findall(r"<h3[^>]*>\s*([^<]+?)\s*</h3>", html):
        name = name.strip()
        if len(name) < 3 or name in skip_titles:
            continue
        names.append(name)
    return names


async def fetch_kaoyana_schools(
    session: ClientSession,
    code: str,
    major_name: str = "",
    max_pages: int = 15,
) -> list[str]:
    """分页抓取研啊考研某专业代码下的开设院校（直连 HTML，比 Jina 更完整）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    skip = {major_name, "招生院校", "开设院校"} if major_name else {"招生院校"}
    all_names: list[str] = []
    seen: set[str] = set()

    for page in range(1, max_pages + 1):
        url = f"https://www.kaoyana.com/major/{code}/"
        if page > 1:
            url += f"?page={page}"
        try:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status != 200:
                    log.warning("kaoyana HTTP %s: %s", resp.status, url)
                    break
                html = await resp.text()
        except Exception as exc:
            log.warning("kaoyana 抓取失败 %s: %s", url, exc)
            break

        batch = _parse_kaoyana_html(html, skip)
        if not batch:
            break
        new = 0
        for n in batch:
            if n not in seen:
                seen.add(n)
                all_names.append(n)
                new += 1
        log.info("kaoyana %s page=%d 新增 %d 校（累计 %d）", code, page, new, len(all_names))
        if new == 0:
            break
        await asyncio.sleep(0.8)
    return all_names


def major_row_from_meta(
    uid: str,
    meta: dict,
    college: str = "",
) -> dict:
    return {
        "university_id": uid,
        "college": college,
        "name": meta["name"],
        "code": meta["code"],
        "degree_type": meta["degree_type"],
        "study_mode": "全日制",
        "subject_category": meta.get("subject_category"),
        "first_discipline": meta.get("first_discipline"),
    }


async def enrich_from_aggregator(
    session: ClientSession,
    db: DB,
    meta: dict,
) -> int:
    """从聚合站导入「某专业 → 多校」关系"""
    lookup, exact = build_uni_lookup(db)
    school_names = await fetch_kaoyana_schools(
        session, meta["code"], major_name=meta.get("name", "")
    )
    if not school_names:
        log.warning("聚合站未获取到 %s 开设院校", meta["name"])
        return 0

    rows: list[dict] = []
    matched = 0
    for sname in school_names:
        uid = resolve_university_id(sname, lookup, exact)
        if not uid:
            continue
        matched += 1
        rows.append(major_row_from_meta(uid, meta))

    rows = dedupe_major_rows(rows)
    if not rows:
        log.warning("%s: 0 所院校匹配到本地库（聚合站 %d 所）", meta["name"], len(school_names))
        return 0

    cnt = db.upsert_majors(rows)
    log.info(
        "[%s %s] 聚合站 %d 所 → 匹配本地 %d 所 → 写入 %d",
        meta["name"],
        meta["code"],
        len(school_names),
        matched,
        cnt,
    )
    return cnt


async def enrich_school_ai(
    session: ClientSession,
    db: DB,
    school_name: str,
) -> int:
    """AI + 多 URL 深挖单校专业目录"""
    meta = db.get_university_meta(school_name)
    uid = meta.get("id") or db.get_university_id(school_name)
    if not uid:
        log.warning("未找到院校: %s", school_name)
        return 0

    seed = next((u for u in __import__("crawl_basic_once").UNIVERSITIES if u["name"] == school_name), {})
    website = seed.get("website", "")
    grad_url = meta.get("graduate_url") or ""

    rows, note = await collect_majors(session, uid, school_name, website, grad_url or None)
    if not rows:
        log.warning("[%s] AI 未提取到专业 (%s)", school_name, note)
        return 0

    cnt = db.upsert_majors(rows)
    log.info("[%s] AI 补采写入 %d 个专业", school_name, cnt)
    return cnt


def schools_with_thin_majors(db: DB, threshold: int = 95) -> list[str]:
    """专业条数偏少的院校（研招网只抓到首页）"""
    uni_res = db._sb.table("universities").select("id,name").execute()
    unis = {u["id"]: u["name"] for u in (uni_res.data or [])}
    counts: dict[str, int] = {uid: 0 for uid in unis}
    offset = 0
    while True:
        r = db._sb.table("majors").select("university_id").range(offset, offset + 999).execute()
        rows = r.data or []
        for row in rows:
            uid = row["university_id"]
            if uid in counts:
                counts[uid] += 1
        if len(rows) < 1000:
            break
        offset += 1000
    return [name for uid, name in unis.items() if counts.get(uid, 0) <= threshold]


def all_university_names(db: DB) -> list[str]:
    res = db._sb.table("universities").select("name").order("name").execute()
    return [r["name"] for r in (res.data or []) if r.get("name")]


async def main(
    popular: bool,
    code: Optional[str],
    school: Optional[str],
    thin: bool,
    thin_limit: int,
    all_schools: bool = False,
) -> None:
    if not os.environ.get("SUPABASE_URL"):
        log.error("缺少 SUPABASE_URL")
        sys.exit(1)

    db = DB()
    connector = TCPConnector(limit=10, ttl_dns_cache=300)
    async with ClientSession(connector=connector) as session:
        total = 0

        if popular or code:
            targets = POPULAR_MAJORS
            if code:
                targets = [m for m in POPULAR_MAJORS if m["code"] == code]
                if not targets:
                    targets = [{
                        "code": code,
                        "name": code,
                        "degree_type": "专硕",
                        "subject_category": None,
                        "first_discipline": None,
                    }]
            for meta in targets:
                total += await enrich_from_aggregator(session, db, meta)
                await asyncio.sleep(2.0)

        if school:
            total += await enrich_school_ai(session, db, school)

        if all_schools:
            names = all_university_names(db)
            log.info("全量 AI 深挖专业 %d 所", len(names))
            for i, name in enumerate(names):
                log.info("── [%d/%d] %s", i + 1, len(names), name)
                try:
                    total += await enrich_school_ai(session, db, name)
                except Exception as exc:
                    log.exception("[%s] 失败: %s", name, exc)
                await asyncio.sleep(2.0)
        elif thin:
            names = schools_with_thin_majors(db)
            if thin_limit > 0:
                names = names[:thin_limit]
            log.info("AI 补采专业偏少院校 %d 所", len(names))
            for i, name in enumerate(names):
                log.info("── [%d/%d] %s", i + 1, len(names), name)
                try:
                    total += await enrich_school_ai(session, db, name)
                except Exception as exc:
                    log.exception("[%s] 失败: %s", name, exc)
                await asyncio.sleep(3.0)

    log.info("补全完成，累计写入/更新 %d 条专业记录", total)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="多源 + AI 补全专业数据")
    parser.add_argument("--popular", action="store_true", help="从聚合站导入热门专业开设院校")
    parser.add_argument("--code", default=None, help="指定专业代码（如 085410）")
    parser.add_argument("--school", default=None, help="AI 深挖单校（精确校名）")
    parser.add_argument(
        "--thin",
        action="store_true",
        help="对专业数≤95 的院校执行 AI 官网补采",
    )
    parser.add_argument(
        "--thin-limit",
        type=int,
        default=0,
        help="--thin 时最多处理 N 所（0=全部）",
    )
    parser.add_argument(
        "--all-schools",
        action="store_true",
        help="对全部院校逐校 AI 深挖专业目录",
    )
    args = parser.parse_args()

    if not any((args.popular, args.code, args.school, args.thin, args.all_schools)):
        parser.error("请指定 --popular / --code / --school / --thin / --all-schools 之一")

    asyncio.run(
        main(
            popular=args.popular,
            code=args.code,
            school=args.school,
            thin=args.thin,
            thin_limit=args.thin_limit,
            all_schools=getattr(args, "all_schools", False),
        )
    )

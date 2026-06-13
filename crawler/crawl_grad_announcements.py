#!/usr/bin/env python3
"""
研究生院官网专项爬虫：招生公告 · 招生简章 · 调剂 · 推免
============================================================
从大学官网 + 研究生院主页出发，自动发现各栏目公告链接，
按标题分类后写入 Supabase（可与 GitHub Actions / pipeline 联动）。

用法：
  python crawl_grad_announcements.py --concurrency 3
  python crawl_grad_announcements.py --school 清华大学 --force
  python crawl_grad_announcements.py --types 招生简章,调剂信息,推免公告
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import sys
import time
from typing import Optional

import aiohttp
from aiohttp import ClientSession, TCPConnector
from dotenv import load_dotenv
from pathlib import Path

_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

os.environ.setdefault("CRAWLER_PARSE_MODEL", "qwen-turbo")

from crawl_updates_smart import (  # noqa: E402
    DB,
    TARGET_YEAR,
    clean_page_content,
    dispatch,
    http_get,
    md5,
    regex_extract_from_markdown,
)
from grad_announcement_sources import (  # noqa: E402
    ANNOUNCEMENT_TYPES,
    build_grad_announcement_urls,
    discover_announcement_urls_from_html,
    discover_site_announcement_urls,
    fetch_detail_items,
    merge_announcement_items,
    parse_grad_list_page,
)
from llm_parser import ParseCache, qwen_extract
from score_sources import fetch_page_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_here / "grad_announcements.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("grad_ann")

MAX_LIST_PAGES = 24
MAX_DETAILS_PER_SCHOOL = 40
MAX_DISCOVER_PER_PAGE = 8


async def _seed_announcement_urls(
    session: ClientSession,
    website: str,
    grad_url: Optional[str],
) -> list[str]:
    """从大学官网 + 研究生院主页发现公告栏目，再合并常见路径。"""
    discovered = await discover_site_announcement_urls(session, website, grad_url)
    return build_grad_announcement_urls(website, grad_url, discovered)


async def _ai_enrich_items(
    combined: str,
    parse_cache: ParseCache,
    force: bool,
) -> list[dict]:
    cleaned = clean_page_content(combined)
    page_hash = md5(cleaned)
    items = await qwen_extract(
        cleaned,
        cache=parse_cache if not force else None,
        content_hash=page_hash,
    )
    if not items:
        items = regex_extract_from_markdown(cleaned)
    if isinstance(items, dict):
        items = [items]
    return [x for x in (items or []) if isinstance(x, dict)]


async def crawl_university(
    session: ClientSession,
    db: DB,
    uni: dict,
    sem: asyncio.Semaphore,
    target_types: set[str],
    force: bool,
    parse_cache: ParseCache,
    fetch_details: bool,
) -> dict:
    name = uni["name"]
    uid = uni["id"]
    stats = {
        "name": name,
        "announcements": 0,
        "adjustments": 0,
        "recommendations": 0,
        "pages": 0,
        "error": None,
    }

    async with sem:
        major_map = db.get_major_map(uid)
        name_map = db.get_major_name_map(uid)
        seed_urls = await _seed_announcement_urls(
            session,
            uni.get("website") or "",
            uni.get("graduate_url"),
        )
        log.debug("[%s] 发现 %d 个候选页面", name, len(seed_urls))

        queue: list[str] = []
        seen: set[str] = set()
        all_items: list[dict] = []
        combined_for_ai: list[str] = []
        website = uni.get("website") or ""
        grad_url = uni.get("graduate_url") or ""

        def _enqueue(u: str) -> None:
            u = (u or "").strip().split("#")[0]
            if u.startswith("http") and u not in seen and len(queue) < MAX_LIST_PAGES * 2:
                seen.add(u)
                queue.append(u)

        for u in seed_urls:
            _enqueue(u)

        while queue and stats["pages"] < MAX_LIST_PAGES:
            url = queue.pop(0)
            if " " in url or not url.startswith("http"):
                continue
            try:
                raw = await fetch_page_text(session, url)
                if not raw or len(raw) < 120:
                    continue
                cleaned = clean_page_content(raw)
                html = await http_get(session, url)
                stats["pages"] += 1

                items = parse_grad_list_page(cleaned, html, url, TARGET_YEAR)
                if not items:
                    items = [
                        x for x in regex_extract_from_markdown(cleaned)
                        if str(x.get("type") or "") in target_types
                    ]

                for it in items:
                    if str(it.get("type") or "") not in target_types:
                        continue
                    key = (it.get("title"), it.get("link"))
                    if key not in {(x.get("title"), x.get("link")) for x in all_items}:
                        all_items.append(it)

                # 从当前页继续发现更多公告栏目（BFS）
                if html and stats["pages"] < MAX_LIST_PAGES:
                    more = discover_announcement_urls_from_html(
                        html, url, website, grad_url
                    )[:MAX_DISCOVER_PER_PAGE]
                    for mu in more:
                        if mu not in seen:
                            _enqueue(mu)

                if len(cleaned) > 300:
                    combined_for_ai.append(cleaned[:2500])

                if len(all_items) >= 30:
                    break

                await asyncio.sleep(random.uniform(0.4, 1.0))
            except Exception as exc:
                log.debug("[%s] 列表 %s: %s", name, url[-50:], exc)

        all_items = merge_announcement_items(all_items)

        # AI 兜底：列表页正则不足时
        if len(all_items) < 2 and combined_for_ai and os.environ.get("DASHSCOPE_API_KEY"):
            try:
                extra = await _ai_enrich_items(
                    "\n\n".join(combined_for_ai)[:8000],
                    parse_cache,
                    force,
                )
                for it in extra:
                    if str(it.get("type") or "") in target_types:
                        all_items.append(it)
            except Exception as exc:
                log.debug("[%s] AI 列表: %s", name, exc)

        # 详情页补正文
        detail_seeds = [
            it for it in all_items
            if it.get("link") and str(it.get("type") or "") in target_types
        ][:MAX_DETAILS_PER_SCHOOL]

        if fetch_details and detail_seeds:
            try:
                detailed = await fetch_detail_items(session, detail_seeds, TARGET_YEAR)
                seen_titles = {d.get("title") for d in detailed}
                rest = [it for it in all_items if it.get("title") not in seen_titles]
                all_items = detailed + rest
            except Exception as exc:
                log.debug("[%s] 详情: %s", name, exc)

        page_hash = md5(f"{name}:{len(all_items)}:{TARGET_YEAR}")
        write = dispatch(
            db,
            uid,
            all_items,
            uni.get("graduate_url") or uni.get("website") or name,
            page_hash,
            list(target_types),
            major_map,
            name_map,
        )
        stats["announcements"] = write.get("announcements", 0)
        stats["adjustments"] = write.get("adjustments", 0)
        stats["recommendations"] = write.get("recommendations", 0)

        total = (
            stats["announcements"]
            + stats["adjustments"]
            + stats["recommendations"]
        )
        if total:
            log.info(
                "[%s] 公告 %d | 调剂 %d | 推免 %d",
                name,
                stats["announcements"],
                stats["adjustments"],
                stats["recommendations"],
            )

    return stats


async def main(
    concurrency: int,
    only_school: Optional[str],
    force: bool,
    types: Optional[list[str]],
    fetch_details: bool,
) -> None:
    if not os.environ.get("DASHSCOPE_API_KEY"):
        log.warning("未配置 DASHSCOPE_API_KEY，将仅用主页发现 + HTML 规则解析")

    target_types = set(types or ANNOUNCEMENT_TYPES)
    db = DB()
    parse_cache = ParseCache()
    universities = db.get_universities()
    if only_school:
        universities = [u for u in universities if only_school in u.get("name", "")]
    if not universities:
        log.error("无院校可处理")
        sys.exit(1)

    log.info(
        "研究生院公告抓取 | 院校 %d | year=%d | types=%s | details=%s",
        len(universities),
        TARGET_YEAR,
        "、".join(sorted(target_types)),
        fetch_details,
    )

    sem = asyncio.Semaphore(concurrency)
    start = time.time()
    connector = TCPConnector(limit=concurrency * 4, ttl_dns_cache=300)

    async with ClientSession(connector=connector) as session:
        results = await asyncio.gather(
            *[
                crawl_university(
                    session,
                    db,
                    uni,
                    sem,
                    target_types,
                    force,
                    parse_cache,
                    fetch_details,
                )
                for uni in universities
            ],
            return_exceptions=True,
        )

    ann = sum(r.get("announcements", 0) for r in results if isinstance(r, dict))
    adj = sum(r.get("adjustments", 0) for r in results if isinstance(r, dict))
    rec = sum(r.get("recommendations", 0) for r in results if isinstance(r, dict))
    schools = sum(
        1
        for r in results
        if isinstance(r, dict)
        and (
            r.get("announcements", 0)
            + r.get("adjustments", 0)
            + r.get("recommendations", 0)
        )
        > 0
    )
    errors = [r for r in results if isinstance(r, Exception)]

    log.info("=" * 60)
    log.info(
        "完成 | 院校 %d | 有数据 %d 所 | 公告 %d | 调剂 %d | 推免 %d | 耗时 %.1fs",
        len(universities),
        schools,
        ann,
        adj,
        rec,
        time.time() - start,
    )
    if errors:
        log.warning("异常 %d 个", len(errors))
    log.info("=" * 60)

    from enrich_postprocess import link_adjustment_major_ids, fix_recommendation_meta
    from notify_frontend import bump_schools_sync

    link_adjustment_major_ids(only_school)
    fix_recommendation_meta(only_school)
    bump_schools_sync("crawl_grad_announcements")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="研究生院招生公告/简章/调剂/推免爬虫")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--school", default=None, help="模糊匹配校名")
    parser.add_argument("--force", action="store_true", help="忽略缓存，全量抓取")
    parser.add_argument(
        "--types",
        default=None,
        help="逗号分隔：招生公告,招生简章,调剂信息,推免公告",
    )
    parser.add_argument(
        "--no-details",
        action="store_true",
        help="只抓列表标题，不跟进详情页",
    )
    args = parser.parse_args()
    type_list = None
    if args.types:
        type_list = [t.strip() for t in args.types.split(",") if t.strip()]

    asyncio.run(
        main(
            concurrency=args.concurrency,
            only_school=args.school,
            force=args.force,
            types=type_list,
            fetch_details=not args.no_details,
        )
    )

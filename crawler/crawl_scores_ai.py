#!/usr/bin/env python3

"""

复试分数线多源 + AI 专项爬虫

============================================================

数据源：EOL 教育在线 + 官网/PDF 附件 + 通义千问兜底。



用法：

  python crawl_scores_ai.py --concurrency 2

  python crawl_scores_ai.py --school 清华 --force

  python crawl_scores_ai.py --limit 20

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



if not os.environ.get("CRAWLER_PARSE_MODEL"):

    os.environ["CRAWLER_PARSE_MODEL"] = "qwen-turbo"



from crawl_updates_smart import (  # noqa: E402

    DB,

    TARGET_YEAR,

    clean_page_content,

    collect_score_detail_urls,

    md5,

    regex_extract_scores,

    upsert_score_from_item,

)

from llm_parser import ParseCache, qwen_extract_scores

from score_sources import (  # noqa: E402

    collect_score_urls_tiered,

    discover_score_links,

    expand_school_line_items,

    fetch_page_text,

    is_valid_crawl_url,

    load_eol_index,

    load_eol_list_articles,

    parse_eol_search_results,

    parse_structured_scores,

    get_major_meta_maps,

)



logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s [%(levelname)s] %(message)s",

    datefmt="%Y-%m-%d %H:%M:%S",

    handlers=[

        logging.StreamHandler(sys.stdout),

        logging.FileHandler(_here / "scores_crawl.log", encoding="utf-8"),

    ],

)

log = logging.getLogger("scores")



MAX_PAGES_PER_SCHOOL = 20

MIN_TEXT_FOR_AI = 400

COMBINED_AI_CHARS = 10_000





def _majors_hint(major_map: dict[str, str], name_map: dict[str, str]) -> str:

    lines = []

    for code, mid in list(major_map.items())[:120]:

        name = next((n for n, i in name_map.items() if i == mid), "")

        lines.append(f"{code} {name}".strip())

    return "\n".join(lines)





def _write_items(

    db: DB,

    uid: str,

    items: list[dict],

    year: int,

    major_map: dict[str, str],

    name_map: dict[str, str],

    expand_school_lines: bool = True,

) -> int:

    if expand_school_lines:

        items = expand_school_line_items(items, major_map)

    written = 0

    for item in items:

        if not isinstance(item, dict):

            continue

        dtype = str(item.get("type") or "复试分数线").strip()

        if dtype not in ("复试分数线", "分数线", "复试线"):

            item["type"] = "复试分数线"

        if upsert_score_from_item(db, uid, item, year, major_map, name_map):

            written += 1

    return written





async def _ai_extract_batch(

    combined: str,

    year: int,

    majors_hint: str,

    parse_cache: ParseCache,

    force: bool,

    cat_map: dict[str, str],

    deg_map: dict[str, str],

    major_map: dict[str, str],

) -> list[dict]:

    cleaned = clean_page_content(combined)

    page_hash = md5(cleaned)

    items = await qwen_extract_scores(

        combined,

        year,

        majors_hint=majors_hint,

        cache=parse_cache if not force else None,

        content_hash=page_hash,

    )

    if not items:

        items = parse_structured_scores(cleaned, year, cat_map, deg_map)

    if not items:

        items = regex_extract_scores(cleaned, year)

    if isinstance(items, dict):

        items = [items]

    return expand_school_line_items(

        [x for x in (items or []) if isinstance(x, dict)],

        major_map,

    )





async def _process_url(

    session: ClientSession,

    url: str,

    name: str,

    cat_map: dict[str, str],

    deg_map: dict[str, str],

) -> tuple[str, list[dict], list[str], list[str]]:

    """返回 (cleaned_text, structured_items, detail_urls, discovered_urls)"""

    from crawl_updates_smart import http_get

    raw = await fetch_page_text(session, url)

    if not raw or len(raw) < 120:

        return "", [], [], []



    if "search/index" in url:

        discovered = parse_eol_search_results(raw, name, TARGET_YEAR)

        return raw, [], [], [u for u in discovered if is_valid_crawl_url(u)]



    cleaned = clean_page_content(raw)

    structured = parse_structured_scores(cleaned, TARGET_YEAR, cat_map, deg_map)

    details = collect_score_detail_urls(cleaned, url)

    html = await http_get(session, url) if "zxgg" in url or "/info/" in url else ""

    discovered = discover_score_links(cleaned, url, TARGET_YEAR, html=html or None)

    return cleaned, structured, details, discovered





async def crawl_university_scores(

    session: ClientSession,

    db: DB,

    uni: dict,

    sem: asyncio.Semaphore,

    parse_cache: ParseCache,

    force: bool,

    detail_limit: int,

    eol_index: dict,

    eol_articles: list[dict],

    no_ai: bool = False,

) -> dict:

    name = uni["name"]

    uid = uni["id"]

    stats = {"name": name, "scores": 0, "pages": 0, "error": None}



    async with sem:

        major_map, cat_map, deg_map = get_major_meta_maps(db, uid)

        name_map = db.get_major_name_map(uid)

        if not major_map:

            log.warning("[%s] 无专业数据，跳过", name)

            return stats



        hint = _majors_hint(major_map, name_map)

        tiers = collect_score_urls_tiered(

            name,

            uni.get("website") or "",

            uni.get("graduate_url"),

            uni.get("school_code"),

            eol_index,

            eol_articles,

            TARGET_YEAR,

        )



        queue: list[str] = []

        seen: set[str] = set()

        combined_parts: list[str] = []

        tier_order = ("eol", "search", "grad", "guess")

        tier_idx = 0



        def _enqueue(u: str) -> None:

            u = (u or "").strip()

            if not is_valid_crawl_url(u):

                return

            key = u.split("#")[0]

            if key not in seen and len(queue) < MAX_PAGES_PER_SCHOOL + detail_limit:

                seen.add(key)

                queue.append(u)



        def _seed_tier(idx: int) -> None:

            if idx >= len(tier_order):

                return

            key = tier_order[idx]

            for u in tiers.get(key) or []:

                _enqueue(u)



        _seed_tier(0)



        while stats["pages"] < MAX_PAGES_PER_SCHOOL:

            if not queue:

                if stats["scores"] < 3 and tier_idx < len(tier_order) - 1:

                    tier_idx += 1

                    _seed_tier(tier_idx)

                if not queue:

                    break

            url = queue.pop(0)

            try:

                cleaned, structured, details, discovered = await _process_url(

                    session, url, name, cat_map, deg_map,

                )

                n = _write_items(

                    db, uid, structured, TARGET_YEAR, major_map, name_map,

                    expand_school_lines=True,

                )

                stats["scores"] += n

                if n:

                    stats["pages"] += 1



                if len(cleaned) >= MIN_TEXT_FOR_AI:

                    combined_parts.append(f"\n--- {url} ---\n{cleaned[:3000]}")



                for d in details:

                    if len([x for x in queue if x]) < detail_limit:

                        _enqueue(d)

                for d in discovered:

                    _enqueue(d)



                if stats["scores"] >= 15:

                    break

                await asyncio.sleep(random.uniform(0.5, 1.2))

            except Exception as exc:

                log.debug("[%s] %s: %s", name, url[-50:], exc)



        if not no_ai and stats["scores"] < 3 and combined_parts:

            combined = "".join(combined_parts)[:COMBINED_AI_CHARS]

            try:

                items = await _ai_extract_batch(

                    combined,

                    TARGET_YEAR,

                    hint,

                    parse_cache,

                    force,

                    cat_map,

                    deg_map,

                    major_map,

                )

                n = _write_items(

                    db, uid, items, TARGET_YEAR, major_map, name_map,

                    expand_school_lines=False,

                )

                if n:

                    stats["scores"] += n

                    stats["pages"] += 1

            except Exception as exc:

                log.debug("[%s] AI 批量: %s", name, exc)



        if stats["scores"]:

            log.info("[%s] 写入复试线 %d 条", name, stats["scores"])



    return stats





async def main(

    concurrency: int,

    only_school: Optional[str],

    force: bool,

    limit: int,

    detail_limit: int,

    refresh_eol: bool,

    no_ai: bool = False,

) -> None:

    if not os.environ.get("DASHSCOPE_API_KEY"):

        log.error("缺少 DASHSCOPE_API_KEY")

        sys.exit(1)



    db = DB()

    parse_cache = ParseCache()

    universities = db.get_universities()

    if only_school:

        universities = [u for u in universities if only_school in u.get("name", "")]

    if limit > 0:

        universities = universities[:limit]

    if not universities:

        log.error("无院校可处理")

        sys.exit(1)



    from llm_parser import _model_chain

    models = _model_chain("CRAWLER_SCORES_MODELS")

    log.info(

        "复试线多源抓取 | 院校 %d | year=%d | force=%s | no_ai=%s | models=%s",

        len(universities),

        TARGET_YEAR,

        force,

        no_ai,

        " → ".join(models),

    )



    sem = asyncio.Semaphore(concurrency)

    start = time.time()

    connector = TCPConnector(limit=concurrency * 4, ttl_dns_cache=300)



    async with ClientSession(connector=connector) as session:

        eol_index = await load_eol_index(session, force=refresh_eol)

        eol_articles = await load_eol_list_articles(session, force=refresh_eol)



        results = await asyncio.gather(

            *[

                crawl_university_scores(

                    session,

                    db,

                    uni,

                    sem,

                    parse_cache,

                    force,

                    detail_limit,

                    eol_index,

                    eol_articles,

                    no_ai,

                )

                for uni in universities

            ],

            return_exceptions=True,

        )



    total_scores = sum(

        r.get("scores", 0) for r in results if isinstance(r, dict)

    )

    schools_with = sum(

        1 for r in results if isinstance(r, dict) and r.get("scores", 0) > 0

    )

    errors = [r for r in results if isinstance(r, Exception)]



    log.info("=" * 60)

    log.info(

        "完成 | 院校 %d | 有数据 %d 所 | 复试线共 %d 条 | 耗时 %.1fs",

        len(universities),

        schools_with,

        total_scores,

        time.time() - start,

    )

    if errors:

        log.warning("异常 %d 个", len(errors))

    log.info("=" * 60)



    from enrich_postprocess import compute_line_diff

    from notify_frontend import bump_schools_sync



    compute_line_diff(only_school)

    bump_schools_sync("crawl_scores_ai")





if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="考研复试分数线多源+AI 爬虫")

    parser.add_argument("--concurrency", type=int, default=2)

    parser.add_argument("--school", default=None, help="模糊匹配校名")

    parser.add_argument("--force", action="store_true", help="忽略页面哈希缓存")

    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 所（0=全部）")

    parser.add_argument("--detail-limit", type=int, default=8, help="每校最多跟进详情页数")

    parser.add_argument(

        "--refresh-eol",

        action="store_true",

        help="强制刷新 EOL 索引/列表缓存",

    )

    parser.add_argument("--no-ai", action="store_true", help="仅用规则/EOL 解析，不调用大模型")

    args = parser.parse_args()

    asyncio.run(

        main(

            concurrency=args.concurrency,

            only_school=args.school,

            force=args.force,

            limit=args.limit,

            detail_limit=args.detail_limit,

            refresh_eol=args.refresh_eol,

            no_ai=args.no_ai,

        )

    )



#!/usr/bin/env python3
"""
择校数据 AI 后处理
============================================================
在爬虫写入后执行结构化补全：
  1. 调剂记录关联 major_id
  2. 分数线补算 line_diff（国家线差）
  3. 推免记录推断 type / status / 时间
  4. AI 补全 majors.college（学院）
  5. 输出覆盖率报告
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

import aiohttp
from aiohttp import ClientSession, TCPConnector
from dotenv import load_dotenv
from supabase import Client, create_client

_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

from crawl_basic_once import ask_qwen, parse_json_safe  # noqa: E402
from crawl_updates_smart import jina_fetch  # noqa: E402
from score_sources import fetch_page_text, grad_announcement_page_urls  # noqa: E402
from enrich_constants import (  # noqa: E402
    TARGET_YEAR,
    extract_dates_from_text,
    infer_rec_status,
    infer_rec_type,
    national_line_for_major,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("postprocess")

COLLEGE_PROMPT = """你是考研招生专家。根据网页内容与专业列表，为每个硕士专业补充所属学院。
只输出 JSON 数组，每项含 code(6位)、name、college(学院全称，必须含"学院/系/中心/研究所"之一)。
找不到学院填 null。不要编造。

专业列表：
{majors}

网页内容：
{content}"""


def _sb() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def _paginate(table: str, select: str, **filters: Any) -> list[dict]:
    sb = _sb()
    rows: list[dict] = []
    offset = 0
    while True:
        q = sb.table(table).select(select)
        for k, v in filters.items():
            q = q.eq(k, v)
        res = q.range(offset, offset + 999).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return rows


def link_adjustment_major_ids(only_school: Optional[str] = None) -> int:
    """调剂记录按专业名/代码关联 majors.id"""
    sb = _sb()
    unis = _paginate("universities", "id,name")
    if only_school:
        unis = [u for u in unis if only_school in u["name"]]

    linked = 0
    for uni in unis:
        uid = uni["id"]
        majors = _paginate("majors", "id,name,code", university_id=uid)
        by_code = {
            re.sub(r"\D", "", m["code"])[:6]: m["id"]
            for m in majors
            if m.get("code")
        }
        by_name = {m["name"]: m["id"] for m in majors if m.get("name")}

        adjs = (
            sb.table("adjustments")
            .select("id,major_id,major_name,year")
            .eq("university_id", uid)
            .eq("year", TARGET_YEAR)
            .execute()
            .data
            or []
        )
        for adj in adjs:
            if adj.get("major_id"):
                continue
            name = (adj.get("major_name") or "").strip()
            if not name or name == "不限":
                continue
            code_m = re.search(r"\d{6}", name)
            mid = None
            if code_m:
                mid = by_code.get(code_m.group())
            if not mid:
                mid = by_name.get(name)
            if not mid:
                for mname, mid2 in by_name.items():
                    if mname in name or name in mname:
                        mid = mid2
                        break
            if mid:
                sb.table("adjustments").update({"major_id": mid}).eq("id", adj["id"]).execute()
                linked += 1
    log.info("调剂 major_id 关联: %d 条", linked)
    return linked


def compute_line_diff(only_school: Optional[str] = None) -> int:
    """为缺失 line_diff 的分数线按国家线补算差值"""
    sb = _sb()
    unis = _paginate("universities", "id,name")
    if only_school:
        unis = [u for u in unis if only_school in u["name"]]

    updated = 0
    for uni in unis:
        uid = uni["id"]
        res = (
            sb.table("scores")
            .select("id,major_id,year,total_score,line_diff,majors(code,subject_category,degree_type)")
            .eq("university_id", uid)
            .eq("year", TARGET_YEAR)
            .execute()
        )
        for row in res.data or []:
            if row.get("line_diff") is not None:
                continue
            total = row.get("total_score")
            if not total:
                continue
            major = row.get("majors") or {}
            nl = national_line_for_major(
                major.get("code"),
                major.get("subject_category"),
                major.get("degree_type"),
            )
            if nl is None:
                continue
            sb.table("scores").update({"line_diff": total - nl}).eq("id", row["id"]).execute()
            updated += 1
    log.info("分数线 line_diff 补算: %d 条", updated)
    return updated


def fix_recommendation_meta(only_school: Optional[str] = None) -> int:
    """推免记录补全 type / status / 起止时间"""
    sb = _sb()
    unis = _paginate("universities", "id,name")
    if only_school:
        unis = [u for u in unis if only_school in u["name"]]

    fixed = 0
    for uni in unis:
        uid = uni["id"]
        res = (
            sb.table("recommendations")
            .select("id,title,type,status,start_time,end_time,content")
            .eq("university_id", uid)
            .execute()
        )
        for row in res.data or []:
            title = row.get("title") or ""
            content = row.get("content") or ""
            patch: dict[str, Any] = {}
            rec_type = infer_rec_type(title)
            if row.get("type") != rec_type:
                patch["type"] = rec_type

            start = row.get("start_time")
            end = row.get("end_time")
            if not start and not end:
                ds, de = extract_dates_from_text(f"{title} {content}")
                if ds:
                    patch["start_time"] = ds
                if de:
                    patch["end_time"] = de
                start = patch.get("start_time", start)
                end = patch.get("end_time", end)

            status = infer_rec_status(
                str(start) if start else None,
                str(end) if end else None,
            )
            if row.get("status") != status:
                patch["status"] = status

            if patch:
                sb.table("recommendations").update(patch).eq("id", row["id"]).execute()
                fixed += 1
    log.info("推免元数据修正: %d 条", fixed)
    return fixed


async def backfill_colleges_ai(
    only_school: Optional[str] = None,
    limit_unis: int = 0,
    batch_size: int = 50,
) -> int:
    """AI 为缺学院的专业补全 college（分批处理）"""
    sb = _sb()
    unis = _paginate("universities", "id,name,graduate_url,website")
    if only_school:
        unis = [u for u in unis if only_school in u["name"]]

    targets: list[tuple[dict, list[dict]]] = []
    for uni in unis:
        majors = _paginate("majors", "id,name,code,college", university_id=uni["id"])
        missing = [
            m
            for m in majors
            if not (m.get("college") or "").strip()
            or m["college"] in ("未知学院", "")
            or not re.search(r"学院|系|中心|部|研究所|研究院", m.get("college") or "")
        ]
        if missing:
            targets.append((uni, missing))

    if limit_unis > 0:
        targets = targets[:limit_unis]

    if not targets:
        log.info("无需补全学院")
        return 0

    updated = 0
    connector = TCPConnector(limit=5)
    async with ClientSession(connector=connector) as session:
        for uni, all_missing in targets:
            uni_updated = 0
            grad = uni.get("graduate_url") or uni.get("website") or ""
            content_parts: list[str] = []
            if grad:
                for page_url in grad_announcement_page_urls(grad)[:6]:
                    part = await fetch_page_text(session, page_url)
                    if part and len(part) > 200:
                        content_parts.append(part[:4000])
                if not content_parts:
                    part = await fetch_page_text(session, grad)
                    if part:
                        content_parts.append(part[:6000])

            content = "\n\n".join(content_parts)
            if len(content) < 300:
                continue

            for offset in range(0, len(all_missing), batch_size):
                missing = all_missing[offset : offset + batch_size]
                majors_json = json.dumps(
                    [{"code": m.get("code"), "name": m.get("name")} for m in missing],
                    ensure_ascii=False,
                )
                prompt = COLLEGE_PROMPT.format(
                    majors=majors_json,
                    content=content[:8000],
                )
                raw = await ask_qwen(prompt)
                parsed = parse_json_safe(raw)
                if not isinstance(parsed, list):
                    continue

                by_code = {
                    re.sub(r"\D", "", str(x.get("code") or ""))[:6]: x
                    for x in parsed
                    if isinstance(x, dict)
                }
                by_name = {
                    str(x.get("name") or "").strip(): x
                    for x in parsed
                    if isinstance(x, dict)
                }

                for m in missing:
                    code = re.sub(r"\D", "", str(m.get("code") or ""))[:6]
                    item = by_code.get(code) if code else None
                    if not item:
                        item = by_name.get(m.get("name") or "")
                    if not isinstance(item, dict):
                        continue
                    college = str(item.get("college") or "").strip()
                    if not college or college == "未知学院":
                        continue
                    if not re.search(r"学院|系|中心|部|研究所|研究院", college):
                        continue
                    sb.table("majors").update({"college": college[:100]}).eq("id", m["id"]).execute()
                    updated += 1
                    uni_updated += 1

                await asyncio.sleep(1.5)

            if uni_updated:
                log.info("[%s] 学院补全 +%d", uni["name"], uni_updated)
            await asyncio.sleep(1.0)

    log.info("AI 学院补全合计: %d 条", updated)
    return updated


def coverage_report() -> dict[str, Any]:
    """择校数据覆盖率快照"""
    sb = _sb()
    uni_count = sb.table("universities").select("id", count="exact").limit(0).execute().count or 0
    maj_count = sb.table("majors").select("id", count="exact").limit(0).execute().count or 0
    score_count = (
        sb.table("scores").select("id", count="exact").eq("year", TARGET_YEAR).limit(0).execute().count
        or 0
    )
    scores_total = sb.table("scores").select("id", count="exact").limit(0).execute().count or 0

    has_majors: set[str] = set()
    offset = 0
    while True:
        r = sb.table("majors").select("university_id").range(offset, offset + 999).execute()
        rows = r.data or []
        has_majors.update(x["university_id"] for x in rows)
        if len(rows) < 1000:
            break
        offset += 1000

    missing_college = 0
    majors_with_college = 0
    offset = 0
    while True:
        r = (
            sb.table("majors")
            .select("id,college")
            .range(offset, offset + 999)
            .execute()
        )
        for row in r.data or []:
            c = (row.get("college") or "").strip()
            if not c or c == "未知学院" or not re.search(r"学院|系|中心|部|研究所|研究院", c):
                missing_college += 1
            else:
                majors_with_college += 1
        if len(r.data or []) < 1000:
            break
        offset += 1000

    ann_count = sb.table("announcements").select("id", count="exact").limit(0).execute().count or 0

    report = {
        "year": TARGET_YEAR,
        "universities": uni_count,
        "universities_with_majors": len(has_majors),
        "universities_missing_majors": uni_count - len(has_majors),
        "majors": maj_count,
        "majors_with_college": majors_with_college,
        "majors_missing_college": missing_college,
        "scores": score_count,
        "scores_total": scores_total,
        "announcements": ann_count,
    }
    log.info("覆盖率报告: %s", json.dumps(report, ensure_ascii=False))
    return report


async def run_postprocess(
    only_school: Optional[str] = None,
    skip_ai_college: bool = False,
    college_limit: int = 30,
) -> None:
    link_adjustment_major_ids(only_school)
    compute_line_diff(only_school)
    fix_recommendation_meta(only_school)
    if not skip_ai_college:
        await backfill_colleges_ai(only_school, limit_unis=college_limit)
    coverage_report()
    from notify_frontend import bump_schools_sync

    bump_schools_sync("postprocess")


def main() -> None:
    parser = argparse.ArgumentParser(description="择校数据 AI 后处理")
    parser.add_argument("--school", default=None, help="仅处理指定院校（模糊匹配）")
    parser.add_argument("--skip-ai-college", action="store_true", help="跳过 AI 学院补全")
    parser.add_argument("--college-limit", type=int, default=30, help="AI 学院补全最多处理 N 所")
    parser.add_argument("--report-only", action="store_true", help="仅输出覆盖率报告")
    args = parser.parse_args()

    if args.report_only:
        coverage_report()
        return

    asyncio.run(
        run_postprocess(
            only_school=args.school,
            skip_ai_college=args.skip_ai_college,
            college_limit=args.college_limit,
        )
    )


if __name__ == "__main__":
    main()

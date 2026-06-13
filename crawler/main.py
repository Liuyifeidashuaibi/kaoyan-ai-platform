#!/usr/bin/env python3
"""
考研择校数据中心 — 爬虫统一入口

用法：
  python main.py patrol            # TOP50 官方来源巡检（默认 CI 日更）
  python main.py update            # 148 校增量官方来源更新
  python main.py full              # 148 校全量来源页发现（不含第三方复试线）
  python main.py school 北京大学     # 单校官方来源发现
  python main.py build-whitelist   # 生成 data/schools.json 白名单
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT.parent / ".env")
load_dotenv(_ROOT.parent / ".env.local")

# 注册 10 校适配器
import adapters.fudan  # noqa: F401, E402
import adapters.generic  # noqa: F401, E402
import adapters.hust  # noqa: F401, E402
import adapters.nju  # noqa: F401, E402
import adapters.peking  # noqa: F401, E402
import adapters.ruc  # noqa: F401, E402
import adapters.sjtu  # noqa: F401, E402
import adapters.tsinghua  # noqa: F401, E402
import adapters.ustc  # noqa: F401, E402
import adapters.whu  # noqa: F401, E402
import adapters.zju  # noqa: F401, E402

from adapters import PRIORITY_SCHOOLS, get_adapter, list_adapters  # noqa: E402
from adapters.generic import run_legacy_college_pipeline, run_legacy_score_pipeline  # noqa: E402
from ai_extract import extract_admission_records, extract_structured  # noqa: E402
from discover import discover_attachments_from_html, is_official_domain  # noqa: E402
from fetchers import fetch_bytes, fetch_page, save_raw  # noqa: E402
from parsers import parse_docx_bytes, parse_excel_bytes, parse_html_to_text, parse_pdf_bytes  # noqa: E402
from graduate_urls import resolve_graduate_url  # noqa: E402
from project_universities import fetch_project_universities  # noqa: E402
from schedulers import push_failed_task  # noqa: E402
from storage import (  # noqa: E402
    ensure_college,
    ensure_major,
    get_client,
    ingest_admission_rows,
    should_skip_by_hash,
    sync_colleges_from_majors,
    sync_school_sources,
    upsert_admission_batch,
    upsert_crawl_task,
    upsert_raw_file_record,
    upsert_score_line,
    upsert_source_page,
    _page_type_to_batch_type,
)

LOG_DIR = _ROOT / "logs"
RAW_DIR = _ROOT / "raw"
SCHOOLS_JSON = _ROOT / "data" / "schools.json"
SCORE_YEARS = [2025, 2026]
ADMISSION_YEARS = [2024, 2025, 2026]


def setup_logging(verbose: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / "crawler.log", encoding="utf-8"),
        ],
    )


def build_whitelist() -> int:
    """从 Supabase universities 生成 schools.json 白名单。"""
    schools = fetch_project_universities()
    payload = {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "count": len(schools),
        "priority": PRIORITY_SCHOOLS,
        "schools": [
            {
                "id": s["id"],
                "name": s["name"],
                "is_985": s.get("level_985", False),
                "is_211": s.get("level_211", False),
                "is_double_first_class": bool(s.get("double_first_class")),
                "province": s.get("province"),
                "city": s.get("city"),
                "school_code": s.get("school_code"),
                "priority": s["name"] in PRIORITY_SCHOOLS,
            }
            for s in schools
        ],
    }
    SCHOOLS_JSON.parent.mkdir(parents=True, exist_ok=True)
    SCHOOLS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.getLogger("main").info("已写入 %s（%d 所）", SCHOOLS_JSON, len(schools))
    return 0


def _load_schools(filter_names: list[str] | None = None) -> list[dict]:
    schools = fetch_project_universities()
    # 合并 school_sources 中的入口 URL
    try:
        sb = get_client()
        src_res = sb.table("school_sources").select("school_name,graduate_url,admission_url,notice_url").execute()
        src_map = {r["school_name"]: r for r in (src_res.data or [])}
        for s in schools:
            src = src_map.get(s["name"]) or {}
            if not s.get("graduate_url"):
                s["graduate_url"] = src.get("graduate_url") or ""
            s["graduate_url"] = resolve_graduate_url(s)
    except Exception as exc:
        logging.getLogger("main").warning("school_sources 合并失败: %s", exc)
        for s in schools:
            s["graduate_url"] = resolve_graduate_url(s)

    if filter_names:
        names = set(filter_names)
        schools = [s for s in schools if s["name"] in names]
    return schools


def _infer_year(title: str, default: int = 2025) -> int:
    import re

    m = re.search(r"(20\d{2})", title or "")
    if m:
        return int(m.group(1))
    return default


def _parse_attachment(data: bytes, url: str) -> str:
    lower = url.lower()
    if lower.endswith(".pdf"):
        return parse_pdf_bytes(data)
    if lower.endswith((".xlsx", ".xls")):
        return parse_excel_bytes(data)
    if lower.endswith((".docx", ".doc")):
        return parse_docx_bytes(data)
    return data.decode("utf-8", errors="ignore")


def _attachment_ext(url: str) -> str:
    from urllib.parse import urlparse

    path = urlparse(url).path.lower()
    for ext in (".pdf", ".xlsx", ".xls", ".docx", ".doc"):
        if path.endswith(ext):
            return ext.lstrip(".")
    return "bin"


def _process_page_content(
    sb,
    *,
    school: dict,
    link: dict,
    content_hash: str,
    raw_path: str,
    publish_date: str | None = None,
    html: str | None = None,
    text: str | None = None,
) -> None:
    """根据页面类型 AI 抽取并入库。"""
    log = logging.getLogger("main.extract")
    page_type = link.get("page_type") or ""
    title = link.get("title") or ""
    body = text if text is not None else parse_html_to_text(html or "")
    uni_id = school["id"]
    year_hint = _infer_year(title)

    if page_type == "复试线":
        for year in SCORE_YEARS:
            rows = extract_structured(body, year=year, school=school["name"])
            for row in rows:
                code = row.get("major_code") or ""
                sl = row.get("score_line") or {}
                total = sl.get("total_score")
                if not code or total is None:
                    continue
                college_id = ensure_college(sb, uni_id, row.get("college", ""))
                major_id = ensure_major(
                    sb,
                    university_id=uni_id,
                    major_code=code,
                    major_name=row.get("major") or "",
                    college=row.get("college") or "",
                    college_id=college_id,
                    source_url=link["url"],
                )
                if not major_id:
                    continue
                upsert_score_line(
                    sb,
                    university_id=uni_id,
                    major_id=major_id,
                    year=year,
                    total=int(total),
                    politics=int(sl.get("politics_score") or 0),
                    english=int(sl.get("english_score") or 0),
                    major_one=sl.get("major_one_score"),
                    major_two=sl.get("major_two_score"),
                    college_id=college_id,
                    source_url=link["url"],
                    confidence=row.get("source_confidence"),
                    publish_date=publish_date,
                )
                log.info("复试线入库 %s %s %s", school["name"], code, year)

    elif page_type in ("拟录取", "复试名单"):
        rows = extract_admission_records(
            body,
            year=year_hint,
            school=school["name"],
            content_hash=content_hash,
        )
        if rows:
            ingest_admission_rows(
                sb,
                university_id=uni_id,
                school_name=school["name"],
                rows=rows,
                source_url=link["url"],
                source_title=title,
                publish_date=publish_date,
                raw_file_path=raw_path,
            )
            log.info("拟录取入库 %s %d 条", school["name"], len(rows))


def _discover_and_register(school: dict, *, incremental: bool = False) -> int:
    """发现来源页并注册到 source_pages。"""
    log = logging.getLogger("main.discover")
    sb = get_client()
    adapter = get_adapter(school["name"])
    uni_id = school["id"]

    if adapter:
        links = adapter.discover_urls(school)
    else:
        from adapters.generic import GenericAdapter

        links = GenericAdapter().discover_urls(school)

    registered = 0
    prefer_pw = bool(adapter and adapter.prefer_playwright())
    queue = list(links)

    for link in queue:
        url = link["url"]
        if not is_official_domain(url):
            continue
        try:
            is_attachment = bool(link.get("is_attachment")) or url.lower().endswith(
                (".pdf", ".xlsx", ".xls", ".doc", ".docx")
            )
            if is_attachment:
                data, chash = fetch_bytes(url)
                ext = _attachment_ext(url)
                body_text = _parse_attachment(data, url)
            else:
                html, chash = fetch_page(url, prefer_playwright=prefer_pw)
                from discover.deep import discover_deep_from_portal

                if link.get("is_hub") or link.get("page_type") == "招生公告":
                    for child in discover_deep_from_portal(html, url):
                        if child["url"] not in {l["url"] for l in queue}:
                            queue.append(child)
                for att in discover_attachments_from_html(html, url):
                    if att["url"] not in {l["url"] for l in queue}:
                        queue.append(att)
                body_text = None

            if incremental and should_skip_by_hash(sb, uni_id, url, chash):
                log.debug("Hash 未变，跳过 %s", url)
                continue

            if is_attachment:
                raw_path = save_raw(
                    RAW_DIR,
                    school_name=school["name"],
                    year=_infer_year(link.get("title") or ""),
                    url=url,
                    content=data,
                    ext=_attachment_ext(url),
                )
            else:
                raw_path = save_raw(
                    RAW_DIR,
                    school_name=school["name"],
                    year=_infer_year(link.get("title") or ""),
                    url=url,
                    content=html,
                    ext="html",
                )

            upsert_source_page(
                sb,
                university_id=uni_id,
                url=url,
                title=link.get("title"),
                page_type=link.get("page_type"),
                content_hash=chash,
                status="ok",
                raw_file_path=str(raw_path),
            )
            year = _infer_year(link.get("title") or "")
            batch_id = upsert_admission_batch(
                sb,
                school_id=uni_id,
                title=link.get("title") or url,
                source_url=url,
                batch_type=_page_type_to_batch_type(link.get("page_type")),
                year=year,
                content_hash=chash,
                verify_status="pending",
            )
            file_ext = _attachment_ext(url) if is_attachment else "html"
            upsert_raw_file_record(
                sb,
                school_id=uni_id,
                file_name=str(raw_path).rsplit("/", 1)[-1].rsplit("\\", 1)[-1],
                file_type=file_ext,
                file_path=str(raw_path),
                file_hash=chash,
                file_size=len(data if is_attachment else (html or "").encode("utf-8")),
                source_url=url,
                batch_id=batch_id,
            )
            registered += 1

            if is_attachment:
                _process_page_content(
                    sb,
                    school=school,
                    link=link,
                    content_hash=chash,
                    raw_path=str(raw_path),
                    text=body_text,
                )
            else:
                _process_page_content(
                    sb,
                    school=school,
                    link=link,
                    content_hash=chash,
                    raw_path=str(raw_path),
                    html=html,
                )
        except Exception as exc:
            log.warning("页面处理失败 %s: %s", url, exc)
            push_failed_task({"school": school["name"], "url": url, "error": str(exc)})
            upsert_crawl_task(
                sb,
                university_id=uni_id,
                school_name=school["name"],
                task_type="fetch",
                target_url=url,
                status="failed",
                error_message=str(exc),
            )
            upsert_source_page(
                sb,
                university_id=uni_id,
                url=url,
                title=link.get("title"),
                page_type=link.get("page_type"),
                content_hash=None,
                status="failed",
            )
    return registered


def cmd_full(args: argparse.Namespace) -> int:
    log = logging.getLogger("main.full")
    log.info("=== 全量官方来源发现开始 ===")

    if args.with_legacy_scores:
        rc = run_legacy_college_pipeline()
        if rc != 0:
            log.warning("学院补全退出码 %d", rc)
        rc = run_legacy_score_pipeline(years=args.years)
        if rc != 0:
            log.error("第三方复试线导入失败，退出码 %d", rc)
            return rc

    targets = _load_schools(PRIORITY_SCHOOLS if args.priority_only else None)
    for school in targets:
        try:
            n = _discover_and_register(school, incremental=False)
            log.info("%s 注册来源页 %d 条", school["name"], n)
        except Exception as exc:
            push_failed_task({"school": school["name"], "mode": "full", "error": str(exc)})

    sync_colleges_from_majors()
    sync_school_sources()

    from notify_frontend import bump_schools_sync

    bump_schools_sync("main.py full")
    log.info("=== 全量官方来源发现完成 ===")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    log = logging.getLogger("main.update")
    log.info("=== 增量更新开始（仅官方来源）===")

    if args.with_legacy_scores:
        rc = run_legacy_score_pipeline(years=args.years)
        if rc != 0:
            log.warning("第三方复试线导入退出码 %d（已跳过不影响官方巡检）", rc)

    schools = _load_schools(PRIORITY_SCHOOLS if args.priority_only else None)
    total = 0
    for school in schools:
        try:
            total += _discover_and_register(school, incremental=True)
        except Exception as exc:
            push_failed_task({"school": school["name"], "mode": "update", "error": str(exc)})

    sync_colleges_from_majors()
    sync_school_sources()

    from notify_frontend import bump_schools_sync

    bump_schools_sync("main.py update")
    log.info("=== 增量更新完成，变更页 %d ===", total)
    return 0


def cmd_school(args: argparse.Namespace) -> int:
    name = args.school_name.strip()
    schools = _load_schools([name])
    if not schools:
        logging.error("未找到学校: %s（可选: %s）", name, ", ".join(list_adapters()))
        return 1

    school = schools[0]
    _discover_and_register(school, incremental=False)
    if args.with_legacy_scores:
        run_legacy_score_pipeline(years=args.years)

    from notify_frontend import bump_schools_sync

    bump_schools_sync(f"main.py school {name}")
    return 0


def cmd_sync_colleges() -> int:
    stats = sync_colleges_from_majors()
    from notify_frontend import bump_schools_sync

    bump_schools_sync("main.py sync-colleges")
    logging.getLogger("main").info("sync-colleges: %s", stats)
    return 0


def cmd_recompute_stats() -> int:
    from storage import recompute_all_statistics

    stats = recompute_all_statistics()
    from notify_frontend import bump_schools_sync

    bump_schools_sync("main.py recompute-stats")
    logging.getLogger("main").info("recompute-stats: %s", stats)
    return 0


def cmd_seed_sources() -> int:
    n = sync_school_sources()
    logging.getLogger("main").info("seed-sources: %d", n)
    return 0


def cmd_discover_priority() -> int:
    """对 TOP50 优先院校做来源页发现（不跑全量复试线）。"""
    log = logging.getLogger("main.discover-priority")
    total = 0
    for school in _load_schools(PRIORITY_SCHOOLS):
        try:
            n = _discover_and_register(school, incremental=False)
            log.info("%s 注册来源页 %d 条", school["name"], n)
            total += n
        except Exception as exc:
            push_failed_task({"school": school["name"], "mode": "discover", "error": str(exc)})
    sync_colleges_from_majors()
    sync_school_sources()
    from notify_frontend import bump_schools_sync

    bump_schools_sync("main.py discover-priority")
    log.info("TOP50 优先校来源页共 %d 条", total)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="考研择校数据中心爬虫")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--years", default="2025-2026", help="复试线年份范围")
    parser.add_argument(
        "--priority-only",
        action="store_true",
        help="仅处理 TOP50 优先校（update/patrol 可用）",
    )
    parser.add_argument(
        "--with-legacy-scores",
        action="store_true",
        help="同时导入掌上考研第三方复试线（默认关闭，数据重建后禁用）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("full", help="148 校全量官方来源发现（不含第三方复试线）")
    sub.add_parser("update", help="增量更新（官方来源，默认全量 148 校）")
    sub.add_parser("patrol", help="官方监控巡检（等同 update，默认 TOP50）")
    sub.add_parser("build-whitelist", help="生成 schools.json")
    sub.add_parser("sync-colleges", help="从 majors 同步 colleges 表")
    sub.add_parser("discover-priority", help="TOP50 优先校来源页发现")
    sub.add_parser("recompute-stats", help="从拟录取记录重算专业统计")
    sub.add_parser("seed-sources", help="同步 school_sources 入口库")

    p_school = sub.add_parser("school", help="单校更新")
    p_school.add_argument("school_name", help="学校名称，如 北京大学")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "build-whitelist":
        return build_whitelist()
    if args.command == "sync-colleges":
        return cmd_sync_colleges()
    if args.command == "discover-priority":
        return cmd_discover_priority()
    if args.command == "recompute-stats":
        return cmd_recompute_stats()
    if args.command == "seed-sources":
        return cmd_seed_sources()
    if args.command == "full":
        return cmd_full(args)
    if args.command == "update":
        return cmd_update(args)
    if args.command == "patrol":
        if not args.priority_only and "--priority-only" not in sys.argv:
            args.priority_only = True
        return cmd_update(args)
    if args.command == "school":
        return cmd_school(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

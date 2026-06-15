"""Supabase 存储层 + Hash 检测 + 拟录取入库 + 统计聚合。"""

from __future__ import annotations

import logging
import os
import statistics as stats_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

_here = Path(__file__).resolve().parents[1]
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

log = logging.getLogger("crawler.storage")


def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def upsert_source_page(
    sb: Client,
    *,
    university_id: str,
    url: str,
    title: str | None,
    page_type: str | None,
    content_hash: str | None,
    status: str = "ok",
    raw_file_path: str | None = None,
    publish_date: str | None = None,
) -> dict[str, Any]:
    row = {
        "university_id": university_id,
        "url": url,
        "title": title,
        "page_type": page_type,
        "content_hash": content_hash,
        "status": status,
        "raw_file_path": raw_file_path,
        "publish_date": publish_date,
        "last_fetch_time": datetime.now(timezone.utc).isoformat(),
    }
    res = sb.table("source_pages").upsert(row, on_conflict="university_id,url").execute()
    return (res.data or [row])[0]


def should_skip_by_hash(sb: Client, university_id: str, url: str, new_hash: str) -> bool:
    """Hash 一致则跳过解析。"""
    res = (
        sb.table("source_pages")
        .select("content_hash,status")
        .eq("university_id", university_id)
        .eq("url", url)
        .maybe_single()
        .execute()
    )
    old = (res.data if res else None) or {}
    if old.get("content_hash") == new_hash and old.get("status") == "ok":
        return True
    return False


def ensure_college(sb: Client, university_id: str, name: str) -> Optional[str]:
    name = (name or "").strip()
    if not name or name == "未知学院":
        return None
    res = (
        sb.table("colleges")
        .upsert(
            {"university_id": university_id, "name": name},
            on_conflict="university_id,name",
        )
        .execute()
    )
    if res.data:
        return res.data[0]["id"]
    q = (
        sb.table("colleges")
        .select("id")
        .eq("university_id", university_id)
        .eq("name", name)
        .maybe_single()
        .execute()
    )
    return (q.data or {}).get("id")


def _page_type_to_batch_type(page_type: str | None) -> str:
    mapping = {
        "招生公告": "招生简章",
        "专业目录": "招生目录",
        "复试线": "复试通知",
        "复试名单": "复试名单",
        "拟录取": "拟录取名单",
    }
    return mapping.get(page_type or "", page_type or "招生简章")


def upsert_admission_batch(
    sb: Client,
    *,
    school_id: str,
    title: str,
    source_url: str,
    batch_type: str,
    year: int,
    content_hash: str | None = None,
    publish_date: str | None = None,
    verify_status: str = "pending",
) -> str | None:
    row = {
        "school_id": school_id,
        "title": title,
        "source_url": source_url,
        "batch_type": batch_type,
        "year": year,
        "content_hash": content_hash,
        "publish_date": publish_date,
        "verify_status": verify_status,
        "crawl_time": datetime.now(timezone.utc).isoformat(),
    }
    res = sb.table("admission_batches").upsert(row, on_conflict="school_id,source_url").execute()
    if res and res.data:
        return res.data[0].get("id")
    q = (
        sb.table("admission_batches")
        .select("id")
        .eq("school_id", school_id)
        .eq("source_url", source_url)
        .maybe_single()
        .execute()
    )
    return ((q.data if q else None) or {}).get("id")


def upsert_raw_file_record(
    sb: Client,
    *,
    school_id: str,
    file_name: str,
    file_type: str,
    file_path: str,
    file_hash: str | None = None,
    file_size: int | None = None,
    source_url: str | None = None,
    batch_id: str | None = None,
) -> None:
    if not file_path:
        return
    existing = (
        sb.table("raw_files")
        .select("id")
        .eq("file_path", file_path)
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        return
    row = {
        "batch_id": batch_id,
        "school_id": school_id,
        "file_name": file_name,
        "file_type": file_type,
        "file_path": file_path,
        "file_hash": file_hash,
        "file_size": file_size,
        "source_url": source_url,
    }
    sb.table("raw_files").insert(row).execute()


def upsert_score_line(
    sb: Client,
    *,
    university_id: str,
    major_id: str,
    year: int,
    total: int,
    politics: int,
    english: int,
    major_one: int | None,
    major_two: int | None,
    college_id: str | None = None,
    source_url: str | None = None,
    confidence: float | None = None,
    remarks: str | None = None,
    publish_date: str | None = None,
) -> None:
    row = {
        "university_id": university_id,
        "major_id": major_id,
        "year": year,
        "total_score": total,
        "politics_score": politics,
        "english_score": english,
        "professional1_score": major_one,
        "professional2_score": major_two,
        "college_id": college_id,
        "source_url": source_url,
        "confidence": confidence,
        "remarks": remarks,
        "score_type": "复试线",
        "publish_date": publish_date,
    }
    sb.table("scores").upsert(row, on_conflict="major_id,year").execute()

    if source_url:
        stat_row = {
            "major_id": major_id,
            "school_id": university_id,
            "college_id": college_id,
            "year": year,
            "retest_line": total,
            "source_url": source_url,
            "publish_date": publish_date,
            "verify_status": "official",
            "crawl_time": datetime.now(timezone.utc).isoformat(),
        }
        sb.table("major_year_stats").upsert(stat_row, on_conflict="major_id,year").execute()


def sync_colleges_from_majors(sb: Client | None = None) -> dict[str, int]:
    """从 majors.college 文本同步到 colleges 表。"""
    import time

    sb = sb or get_client()
    stats = {"colleges": 0}
    seen: set[tuple[str, str]] = set()
    offset = 0

    while True:
        last_err: Exception | None = None
        batch = []
        for attempt in range(4):
            try:
                res = (
                    sb.table("majors")
                    .select("university_id,college")
                    .not_.is_("college", "null")
                    .range(offset, offset + 999)
                    .execute()
                )
                batch = res.data or []
                break
            except Exception as exc:
                last_err = exc
                time.sleep(1.5 * (attempt + 1))
        if last_err and not batch:
            raise last_err

        for row in batch:
            college = (row.get("college") or "").strip()
            uid = row.get("university_id")
            if not uid or not college or college == "未知学院":
                continue
            key = (uid, college)
            if key in seen:
                continue
            seen.add(key)
            if ensure_college(sb, uid, college):
                stats["colleges"] += 1
        if len(batch) < 1000:
            break
        offset += 1000

    log.info("学院同步完成: %d 学院", stats["colleges"])
    return stats


def ensure_major(
    sb: Client,
    *,
    university_id: str,
    major_code: str,
    major_name: str = "",
    college: str = "",
    college_id: str | None = None,
    degree_type: str = "学硕",
    study_mode: str = "全日制",
    source_url: str | None = None,
) -> str | None:
    """查找或创建专业，返回 major_id。"""
    code = (major_code or "").strip()
    if len(code) < 6:
        return None
    code = code[:6]

    for dt in (degree_type, "学硕", "专硕"):
        res = (
            sb.table("majors")
            .select("id")
            .eq("university_id", university_id)
            .eq("code", code)
            .eq("degree_type", dt)
            .eq("study_mode", study_mode)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["id"]

    name = (major_name or f"专业{code}").strip() or f"专业{code}"
    college_name = (college or "未知学院").strip() or "未知学院"
    if not college_id and college_name != "未知学院":
        college_id = ensure_college(sb, university_id, college_name)

    row = {
        "university_id": university_id,
        "code": code,
        "name": name,
        "college": college_name,
        "college_id": college_id,
        "degree_type": degree_type,
        "study_mode": study_mode,
        "source_url": source_url,
        "status": "active",
    }
    res = sb.table("majors").upsert(row, on_conflict="university_id,code,degree_type,study_mode").execute()
    if res.data:
        return res.data[0]["id"]
    q = (
        sb.table("majors")
        .select("id")
        .eq("university_id", university_id)
        .eq("code", code)
        .eq("degree_type", degree_type)
        .eq("study_mode", study_mode)
        .maybe_single()
        .execute()
    )
    return (q.data or {}).get("id")


def upsert_admission_record(
    sb: Client,
    *,
    university_id: str,
    year: int,
    initial_score: int,
    major_id: str | None = None,
    college_id: str | None = None,
    candidate_no: str | None = None,
    candidate_name: str | None = None,
    retest_score: int | None = None,
    final_score: int | None = None,
    admission_status: str = "拟录取",
    source_url: str | None = None,
    source_title: str | None = None,
    publish_date: str | None = None,
    raw_file_path: str | None = None,
) -> None:
    row = {
        "university_id": university_id,
        "major_id": major_id,
        "college_id": college_id,
        "year": year,
        "candidate_no": candidate_no,
        "candidate_name": candidate_name,
        "initial_score": initial_score,
        "retest_score": retest_score,
        "final_score": final_score,
        "admission_status": admission_status,
        "source_url": source_url,
        "source_title": source_title,
        "publish_date": publish_date,
        "raw_file_path": raw_file_path,
    }
    sb.table("admission_records").insert(row).execute()


def ingest_admission_rows(
    sb: Client,
    *,
    university_id: str,
    school_name: str,
    rows: list[dict[str, Any]],
    source_url: str,
    source_title: str | None = None,
    publish_date: str | None = None,
    raw_file_path: str | None = None,
) -> dict[str, int]:
    """批量写入拟录取记录并触发统计。"""
    stats = {"records": 0, "majors": 0}
    affected: set[tuple[str, int]] = set()

    # 同一来源重新抓取时先清除旧记录，保证幂等
    sb.table("admission_records").delete().eq("source_url", source_url).execute()

    for row in rows:
        code = (row.get("major_code") or "").strip()
        yr = int(row.get("year") or 2025)
        initial = row.get("initial_score")
        if initial is None:
            continue
        college_name = row.get("college") or ""
        college_id = ensure_college(sb, university_id, college_name) if college_name else None
        major_id = ensure_major(
            sb,
            university_id=university_id,
            major_code=code,
            major_name=row.get("major") or "",
            college=college_name,
            college_id=college_id,
            source_url=source_url,
        )
        if not major_id:
            continue

        upsert_admission_record(
            sb,
            university_id=university_id,
            year=yr,
            initial_score=int(initial),
            major_id=major_id,
            college_id=college_id,
            candidate_no=row.get("candidate_no"),
            candidate_name=row.get("candidate_name"),
            retest_score=row.get("retest_score"),
            final_score=row.get("final_score"),
            admission_status=row.get("admission_status") or "拟录取",
            source_url=source_url,
            source_title=source_title,
            publish_date=publish_date,
            raw_file_path=raw_file_path,
        )
        stats["records"] += 1
        affected.add((major_id, yr))

    for major_id, yr in affected:
        recompute_major_statistics(
            sb,
            major_id=major_id,
            year=yr,
            source_url=source_url,
            source_title=source_title,
            publish_date=publish_date,
            raw_file_path=raw_file_path,
        )
        stats["majors"] += 1

    log.info("%s 拟录取入库 %d 条，更新 %d 个专业统计", school_name, stats["records"], stats["majors"])
    return stats


def recompute_major_statistics(
    sb: Client,
    *,
    major_id: str,
    year: int,
    source_url: str | None = None,
    source_title: str | None = None,
    publish_date: str | None = None,
    raw_file_path: str | None = None,
) -> dict[str, Any] | None:
    """从 admission_records 聚合 min/avg/max 并写入 major_statistics。"""
    res = (
        sb.table("admission_records")
        .select("initial_score,university_id,college_id")
        .eq("major_id", major_id)
        .eq("year", year)
        .eq("admission_status", "拟录取")
        .execute()
    )
    rows = res.data or []
    scores = [int(r["initial_score"]) for r in rows if r.get("initial_score") is not None]
    if not scores:
        return None

    university_id = rows[0]["university_id"]
    college_id = rows[0].get("college_id")
    min_score = min(scores)
    max_score = max(scores)
    avg_score = round(stats_module.mean(scores), 2)

    retest_res = (
        sb.table("admission_records")
        .select("id", count="exact")
        .eq("major_id", major_id)
        .eq("year", year)
        .neq("admission_status", "拟录取")
        .execute()
    )
    retest_count = int(retest_res.count or 0)

    retest_line = None
    score_res = (
        sb.table("scores")
        .select("total_score")
        .eq("major_id", major_id)
        .eq("year", year)
        .maybe_single()
        .execute()
    )
    if score_res.data:
        retest_line = score_res.data.get("total_score")

    admission_rate = None
    if retest_count and retest_count > 0:
        admission_rate = round(len(scores) / retest_count, 4)

    stat_row = {
        "university_id": university_id,
        "college_id": college_id,
        "major_id": major_id,
        "year": year,
        "min_score": min_score,
        "avg_score": avg_score,
        "max_score": max_score,
        "admitted_count": len(scores),
        "retest_count": retest_count or None,
        "admission_rate": admission_rate,
        "retest_line": retest_line,
        "source_url": source_url,
        "source_title": source_title,
        "publish_date": publish_date,
        "raw_file_path": raw_file_path,
    }
    sb.table("major_statistics").upsert(stat_row, on_conflict="major_id,year").execute()
    return stat_row


def recompute_all_statistics(sb: Client | None = None) -> dict[str, int]:
    """全量重算 major_statistics。"""
    sb = sb or get_client()
    stats = {"updated": 0}
    offset = 0
    seen: set[tuple[str, int]] = set()

    while True:
        res = (
            sb.table("admission_records")
            .select("major_id,year")
            .not_.is_("major_id", "null")
            .range(offset, offset + 999)
            .execute()
        )
        batch = res.data or []
        for row in batch:
            key = (row["major_id"], int(row["year"]))
            if key in seen:
                continue
            seen.add(key)
            if recompute_major_statistics(sb, major_id=key[0], year=key[1]):
                stats["updated"] += 1
        if len(batch) < 1000:
            break
        offset += 1000

    log.info("统计重算完成: %d 个专业年度", stats["updated"])
    return stats


def upsert_crawl_task(
    sb: Client,
    *,
    university_id: str | None,
    school_name: str | None,
    task_type: str,
    target_url: str | None = None,
    status: str = "pending",
    priority: int = 0,
    error_message: str | None = None,
    payload: dict | None = None,
) -> None:
    row = {
        "university_id": university_id,
        "school_name": school_name,
        "task_type": task_type,
        "target_url": target_url,
        "status": status,
        "priority": priority,
        "error_message": error_message,
        "payload": payload or {},
        "finished_at": datetime.now(timezone.utc).isoformat() if status in ("ok", "failed") else None,
    }
    sb.table("crawl_tasks").insert(row).execute()


def sync_school_sources(sb: Client | None = None) -> int:
    """从 universities 同步 school_sources 入口库。"""
    sb = sb or get_client()
    count = 0
    offset = 0
    while True:
        res = (
            sb.table("universities")
            .select("id,name,graduate_url,website")
            .range(offset, offset + 999)
            .execute()
        )
        batch = res.data or []
        for uni in batch:
            sb.table("school_sources").upsert(
                {
                    "university_id": uni["id"],
                    "school_name": uni["name"],
                    "graduate_url": uni.get("graduate_url") or uni.get("website"),
                    "status": "active",
                },
                on_conflict="school_name",
            ).execute()
            count += 1
        if len(batch) < 1000:
            break
        offset += 1000
    log.info("school_sources 同步 %d 条", count)
    return count

#!/usr/bin/env python3
"""
择校数据重建脚本（Phase 2–10）

用法：
  python data_rebuild.py --dry-run          # 仅预览，不写库
  python data_rebuild.py                    # 执行完整重建
  python data_rebuild.py --skip-sql         # 跳过 SQL 迁移（已手动执行时）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

_here = Path(__file__).parent
_root = _here.parent
load_dotenv(_here / ".env")
load_dotenv(_root / ".env.local")

from crawl_basic_once import (  # noqa: E402
    _is_likely_college_name,
    is_likely_major_code,
    is_valid_major_name,
)

SUBJECT_CATEGORIES = {
    "哲学", "经济学", "法学", "教育学", "文学", "历史学", "理学", "工学",
    "农学", "医学", "军事学", "管理学", "艺术学",
}

REBUILD_DATE = "2026-06-14"
REPORT_PATH = _here / "logs" / "data_rebuild_report.json"


def sb() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def fetch_all(client: Client, table: str, cols: str, retries: int = 5) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        last_err: Exception | None = None
        chunk: list[dict] = []
        for attempt in range(retries):
            try:
                chunk = (
                    client.table(table)
                    .select(cols)
                    .range(offset, offset + 999)
                    .execute()
                    .data
                    or []
                )
                last_err = None
                break
            except Exception as exc:
                last_err = exc
                time.sleep(1.5 * (attempt + 1))
        if last_err is not None:
            raise last_err
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < 1000:
            break
        offset += 1000
    return rows


def count_table(client: Client, table: str) -> int:
    try:
        return client.table(table).select("id", count="exact").limit(0).execute().count or 0
    except Exception:
        return -1


def run_sql_migrations() -> None:
    node = "node"
    for mig in ("010_data_rebuild.sql", "011_data_rebuild_purge.sql"):
        cmd = [node, str(_root / "scripts" / "run-migration.mjs"), mig]
        print(f"  运行迁移: {mig}")
        subprocess.run(cmd, cwd=str(_root), check=True)


def batch_delete(client: Client, table: str, ids: list[str], dry_run: bool) -> int:
    if not ids or dry_run:
        return len(ids)
    deleted = 0
    for i in range(0, len(ids), 80):
        chunk = ids[i : i + 80]
        client.table(table).delete().in_("id", chunk).execute()
        deleted += len(chunk)
    return deleted


def phase4_validate_majors(client: Client, dry_run: bool) -> dict:
    """专业库校验：删噪声、修正学院、补 colleges、绑 college_id。"""
    majors = fetch_all(
        client,
        "majors",
        "id,university_id,name,code,college,college_id,degree_type,study_mode,subject_category,first_discipline,status,source_url",
    )
    deleted_majors: list[dict] = []
    fixed_colleges: list[dict] = []
    to_delete: list[str] = []

    for row in majors:
        mid = row["id"]
        name = row.get("name") or ""
        code = (row.get("code") or "").replace(" ", "")
        digits = "".join(c for c in code if c.isdigit())
        college = (row.get("college") or "").strip()
        first_d = (row.get("first_discipline") or "").strip()
        subject = (row.get("subject_category") or "").strip()

        if not is_valid_major_name(name) or not is_likely_major_code(digits):
            to_delete.append(mid)
            deleted_majors.append({"id": mid, "name": name, "code": code, "reason": "invalid_name_or_code"})
            continue

        should_clear = (
            college
            and (
                college == "未知学院"
                or college == first_d
                or college == subject
                or college in SUBJECT_CATEGORIES
                or not _is_likely_college_name(college)
            )
        )
        if should_clear:
            fixed_colleges.append({"id": mid, "old_college": college, "new_college": ""})

    deleted_count = batch_delete(client, "majors", to_delete, dry_run)

    if not dry_run:
        for i in range(0, len(fixed_colleges), 50):
            chunk = fixed_colleges[i : i + 50]
            for patch in chunk:
                client.table("majors").update({"college": ""}).eq("id", patch["id"]).execute()
            time.sleep(0.2)

    # 从 majors.college 同步 colleges 表
    if not dry_run:
        # 幂等 SQL 同步
        sync_sql_path = _root / "supabase" / "migrations" / "008_sync_colleges_bulk.sql"
        if sync_sql_path.exists():
            subprocess.run(
                [node_or("node"), str(_root / "scripts" / "run-migration.mjs"), "008_sync_colleges_bulk.sql"],
                cwd=str(_root),
                check=False,
            )

    colleges = fetch_all(client, "colleges", "id,university_id,name")
    college_lookup = {(c["university_id"], c["name"]): c["id"] for c in colleges}

    # college_id 绑定由 012 SQL 批量完成；此处仅统计待绑数量
    majors_after = fetch_all(client, "majors", "id,university_id,college,college_id")
    pending_before = sum(
        1
        for m in majors_after
        if (m.get("college") or "").strip() and not m.get("college_id")
    )
    new_colleges: list[dict] = []
    for m in majors_after:
        uni_id = m["university_id"]
        college_name = (m.get("college") or "").strip()
        if not college_name or m.get("college_id"):
            continue
        if (uni_id, college_name) not in college_lookup and _is_likely_college_name(college_name):
            new_colleges.append({"university_id": uni_id, "name": college_name})
            if not dry_run:
                try:
                    ins = (
                        client.table("colleges")
                        .insert({"university_id": uni_id, "name": college_name})
                        .execute()
                    )
                    if ins.data:
                        college_lookup[(uni_id, college_name)] = ins.data[0]["id"]
                except Exception:
                    pass

    linked = pending_before
    if not dry_run and (new_colleges or pending_before):
        subprocess.run(
            [node_or("node"), str(_root / "scripts" / "run-migration.mjs"), "012_data_rebuild_finalize.sql"],
            cwd=str(_root),
            check=False,
        )
        majors_linked = fetch_all(client, "majors", "college_id")
        linked = sum(1 for m in majors_linked if m.get("college_id"))

    # orphan colleges 由 012 SQL 迁移处理
    orphan_colleges: list[str] = []

    return {
        "deleted_majors_count": deleted_count,
        "deleted_majors_sample": deleted_majors[:30],
        "fixed_college_text_count": len(fixed_colleges),
        "linked_college_id_count": linked,
        "pending_college_id_before_sql": pending_before,
        "new_colleges_count": len(new_colleges),
        "new_colleges_sample": new_colleges[:20],
        "orphan_colleges_deleted": len(orphan_colleges) if not dry_run else "skipped",
    }


def phase5_master_data(client: Client, dry_run: bool) -> dict:
    """补全专业主数据字段（012 SQL 已在 phase4 末尾执行，此处仅确认）。"""
    if dry_run:
        majors = fetch_all(client, "majors", "id,degree_type,master_type,status,last_verified_at")
        need = sum(
            1
            for m in majors
            if not m.get("master_type")
            or not m.get("status")
            or not m.get("last_verified_at")
        )
        return {"majors_master_fields_updated": need, "method": "dry_run_estimate"}

    if not dry_run:
        # phase4 可能已执行 012；幂等再跑一次确保 master 字段完整
        subprocess.run(
            [node_or("node"), str(_root / "scripts" / "run-migration.mjs"), "012_data_rebuild_finalize.sql"],
            cwd=str(_root),
            check=False,
        )
    return {"majors_master_fields_updated": "all_via_sql", "method": "012_data_rebuild_finalize.sql"}


def phase6_seed_source_sites(client: Client, dry_run: bool) -> dict:
    """从 universities / school_sources 初始化 source_sites。"""
    unis = fetch_all(client, "universities", "id,name,graduate_url,website")
    sources = fetch_all(client, "school_sources", "university_id,graduate_url,admission_url,notice_url,college_urls")
    src_by_uni = {s["university_id"]: s for s in sources if s.get("university_id")}

    inserted = 0
    for u in unis:
        uid = u["id"]
        src = src_by_uni.get(uid, {})
        entries: list[tuple[str, str | None]] = [
            ("graduate_school", src.get("graduate_url") or u.get("graduate_url")),
            ("admission_site", src.get("admission_url")),
            ("notice_site", src.get("notice_url")),
        ]
        if not src.get("graduate_url") and u.get("website"):
            entries.append(("graduate_school", u["website"]))

        college_urls = src.get("college_urls") or []
        if isinstance(college_urls, list):
            for cu in college_urls:
                url = cu if isinstance(cu, str) else cu.get("url")
                if url:
                    entries.append(("college_site", url))

        for site_type, url in entries:
            if not url or not str(url).startswith("http"):
                continue
            row = {
                "school_id": uid,
                "site_type": site_type,
                "url": str(url).strip(),
                "status": "active",
            }
            if dry_run:
                inserted += 1
                continue
            try:
                client.table("source_sites").upsert(row, on_conflict="school_id,site_type,url").execute()
                inserted += 1
            except Exception:
                try:
                    client.table("source_sites").insert(row).execute()
                    inserted += 1
                except Exception:
                    pass

    return {"source_sites_seeded": inserted}


def node_or(default: str) -> str:
    return default


def build_report(client: Client, actions: dict) -> dict:
    return {
        "rebuild_date": REBUILD_DATE,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "final_counts": {
            "schools": count_table(client, "universities"),
            "colleges": count_table(client, "colleges"),
            "majors": count_table(client, "majors"),
            "scores": count_table(client, "scores"),
            "admission_records": count_table(client, "admission_records"),
            "major_statistics": count_table(client, "major_statistics"),
            "major_year_stats": count_table(client, "major_year_stats"),
            "admission_batches": count_table(client, "admission_batches"),
            "raw_files": count_table(client, "raw_files"),
            "source_sites": count_table(client, "source_sites"),
            "parse_jobs": count_table(client, "parse_jobs"),
        },
        "actions": actions,
        "new_schema_tables": [
            "source_sites",
            "admission_batches",
            "raw_files",
            "major_year_stats",
            "parse_jobs",
        ],
        "data_rules_from": REBUILD_DATE,
        "verify_status_values": ["official", "pending", "invalid"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="择校数据重建")
    parser.add_argument("--dry-run", action="store_true", help="仅预览")
    parser.add_argument("--skip-sql", action="store_true", help="跳过 SQL 迁移")
    args = parser.parse_args()

    client = sb()
    actions: dict = {"dry_run": args.dry_run}

    print("=" * 60)
    print("Phase 2: 保留 universities / colleges / majors")
    print("=" * 60)
    before = {
        "universities": count_table(client, "universities"),
        "colleges": count_table(client, "colleges"),
        "majors": count_table(client, "majors"),
        "scores": count_table(client, "scores"),
        "announcements": count_table(client, "announcements"),
        "recommendations": count_table(client, "recommendations"),
        "adjustments": count_table(client, "adjustments"),
        "admission_records": count_table(client, "admission_records"),
    }
    actions["before_counts"] = before
    print(json.dumps(before, ensure_ascii=False, indent=2))

    if not args.dry_run and not args.skip_sql:
        print("\n" + "=" * 60)
        print("Phase 3 + Schema: SQL 迁移 & 清除不可信数据")
        print("=" * 60)
        run_sql_migrations()
        actions["sql_migrations"] = ["010_data_rebuild.sql", "011_data_rebuild_purge.sql"]
    elif args.skip_sql:
        actions["sql_migrations"] = "skipped"
    else:
        actions["sql_migrations"] = "dry_run_skipped"

    print("\n" + "=" * 60)
    print("Phase 4: 专业库校验")
    print("=" * 60)
    p4 = phase4_validate_majors(client, args.dry_run)
    actions["phase4"] = p4
    print(json.dumps(p4, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    print("Phase 5: 专业主数据补全")
    print("=" * 60)
    p5 = phase5_master_data(client, args.dry_run)
    actions["phase5"] = p5
    print(json.dumps(p5, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    print("Phase 6: 初始化 source_sites")
    print("=" * 60)
    p6 = phase6_seed_source_sites(client, args.dry_run)
    actions["phase6"] = p6
    print(json.dumps(p6, ensure_ascii=False, indent=2))

    report = build_report(client, actions)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("Phase 10: 最终报告")
    print("=" * 60)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.dry_run:
        print(f"\n报告已保存: {REPORT_PATH}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
择校项目清理：本地缓存 + 数据库噪声
============================================================
用法：
  python cleanup_project.py --files          # 仅清本地缓存/临时文件
  python cleanup_project.py --db             # 仅清数据库噪声
  python cleanup_project.py --all            # 全部（默认）
  python cleanup_project.py --all --dry-run  # 预览，不写库
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_here = Path(__file__).parent
_root = _here.parent
load_dotenv(_here / ".env")
load_dotenv(_root / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cleanup")

# 保留的数据缓存（勿删）
_KEEP_DATA = {
    "school_codes.json",
    "eol_score_index.json",
    "kaoyan_school_id_map.json",
    "kaoyan_scores_985_211.csv",
}


def _sb():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def clean_local_files() -> dict[str, int]:
    """删除构建缓存、爬虫日志、调试样本。"""
    stats = {"deleted_files": 0, "deleted_dirs": 0, "freed_hint": 0}

    def rm_file(p: Path) -> None:
        if p.is_file():
            try:
                stats["freed_hint"] += p.stat().st_size
                p.unlink()
                stats["deleted_files"] += 1
                log.info("删除文件 %s", p.relative_to(_root))
            except OSError as exc:
                log.warning("无法删除 %s: %s", p, exc)

    def rm_dir(p: Path) -> None:
        if p.is_dir():
            try:
                shutil.rmtree(p)
                stats["deleted_dirs"] += 1
                log.info("删除目录 %s", p.relative_to(_root))
            except OSError as exc:
                log.warning("无法删除目录 %s: %s", p, exc)

    # Next.js 构建缓存
    rm_dir(_root / ".next")

    # 爬虫日志
    for p in _here.glob("*.log"):
        rm_file(p)

    # 调试 HTML / 文本样本
    for pattern in ("_*.html", "*_sample.txt", "*_sample.html", "*_debug.log", "*_probe_out.txt"):
        for p in _here.glob(pattern):
            rm_file(p)
    for name in ("zxgg.txt", "tsinghua_sample.txt", "eol_search_sample.txt", "eol_probe_out.txt"):
        rm_file(_here / name)

    # LLM 解析缓存（可重建）
    rm_file(_here / "parse_cache.json")

    # 旧版全量爬虫检查点（择校已用 pipeline_enrich）
    rm_file(_here / "crawler_checkpoint.json")

    # 测试 CSV（正式全量 CSV 保留）
    test_csv = _here / "data" / "kaoyan_scores_whu_test.csv"
    if test_csv.is_file() and not (_here / "data" / "kaoyan_scores_985_211.csv").is_file():
        log.info("保留试跑 CSV（尚无全量文件）: %s", test_csv.name)
    else:
        rm_file(test_csv)

    # TypeScript 增量缓存
    for p in _root.glob("*.tsbuildinfo"):
        rm_file(p)

    return stats


def _paginate(table: str, select: str, page_size: int = 1000) -> list[dict]:
    sb = _sb()
    offset = 0
    rows: list[dict] = []
    while True:
        res = sb.table(table).select(select).range(offset, offset + page_size - 1).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def _batch_delete(table: str, ids: list[str], *, dry_run: bool, chunk: int = 80) -> int:
    if not ids or dry_run:
        return len(ids) if dry_run else 0
    sb = _sb()
    deleted = 0
    for i in range(0, len(ids), chunk):
        chunk_ids = ids[i : i + chunk]
        sb.table(table).delete().in_("id", chunk_ids).execute()
        deleted += len(chunk_ids)
    return deleted


def clean_database(*, dry_run: bool = False) -> dict[str, Any]:
    """清 majors 噪声、异常分数线。"""
    report: dict[str, Any] = {}

    # 1) majors 噪声 — 复用 cleanup_majors.py
    log.info("═══ 专业噪声清理 ═══")
    cmd = [sys.executable, str(_here / "cleanup_majors.py")]
    if dry_run:
        log.info("[dry-run] 跳过 cleanup_majors 执行")
    else:
        subprocess.run(cmd, cwd=str(_here), check=False)

    sb = _sb()

    log.info("═══ 分数线异常清理 ═══")
    score_rows = _paginate("scores", "id,total_score,year")
    score_delete = [
        r["id"]
        for r in score_rows
        if (r.get("total_score") or 0) <= 0 or (r.get("total_score") or 0) > 500
    ]
    report["scores_junk"] = len(score_delete)
    report["scores_deleted"] = _batch_delete("scores", score_delete, dry_run=dry_run)
    log.info("分数线待删 %d，已删 %d", len(score_delete), report["scores_deleted"])

    # 4) 孤儿调剂/推免
    adj_rows = _paginate("adjustments", "id,major_name,url")
    adj_junk = [r["id"] for r in adj_rows if len((r.get("major_name") or "").strip()) < 2]
    adj_deleted = _batch_delete("adjustments", adj_junk, dry_run=dry_run)
    report["adjustments_junk"] = len(adj_junk)
    report["adjustments_deleted"] = adj_deleted
    log.info("adjustments 待删 %d，已删 %d", len(adj_junk), adj_deleted)

    rec_rows = _paginate("recommendations", "id,title,url")
    rec_junk = [r["id"] for r in rec_rows if len((r.get("title") or "").strip()) < 3]
    rec_deleted = _batch_delete("recommendations", rec_junk, dry_run=dry_run)
    report["recommendations_junk"] = len(rec_junk)
    report["recommendations_deleted"] = rec_deleted
    log.info("recommendations 待删 %d，已删 %d", len(rec_junk), rec_deleted)

    # 5) bump 前端同步版本
    if not dry_run:
        try:
            from notify_frontend import bump_schools_sync

            rev = bump_schools_sync("cleanup_project")
            report["sync_revision"] = rev
        except Exception as exc:
            log.warning("同步版本 bump 失败: %s", exc)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="择校项目清理")
    parser.add_argument("--files", action="store_true", help="仅清本地文件")
    parser.add_argument("--db", action="store_true", help="仅清数据库")
    parser.add_argument("--all", action="store_true", help="全部清理")
    parser.add_argument("--dry-run", action="store_true", help="数据库预览模式")
    args = parser.parse_args()

    do_files = args.files or args.all or (not args.files and not args.db)
    do_db = args.db or args.all or (not args.files and not args.db)

    if do_files:
        log.info("═══ 本地缓存清理 ═══")
        fs = clean_local_files()
        log.info("本地清理完成: %s", fs)

    if do_db:
        log.info("═══ 数据库清理 ═══")
        db = clean_database(dry_run=args.dry_run)
        log.info("数据库清理完成: %s", db)

    # 覆盖率
    if do_db and not args.dry_run:
        subprocess.run(
            [sys.executable, str(_here / "pipeline_enrich.py"), "verify"],
            cwd=str(_here),
            check=False,
        )


if __name__ == "__main__":
    main()

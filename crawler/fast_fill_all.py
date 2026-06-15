#!/usr/bin/env python3
"""
一键快速补全择校数据（学院 + 复试线）
============================================================
优化：CRAWLER_FAST=1、跳过研招网、多校并行、院系页并行抓取。

用法：
  python fast_fill_all.py
  python fast_fill_all.py --offset 12        # 断点续跑
  python fast_fill_all.py --scores-only
  python fast_fill_all.py --colleges-only
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_here = Path(__file__).parent
os.environ.setdefault("CRAWLER_FAST", "1")

CSV_OUT = _here / "data" / "kaoyan_scores_985_211.csv"


def run(cmd: list[str], label: str) -> int:
    print(f"\n═══ {label} ═══", flush=True)
    print(" ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(_here))


def main() -> None:
    parser = argparse.ArgumentParser(description="快速补全学院+复试线")
    parser.add_argument("--offset", type=int, default=0, help="跳过前 N 校")
    parser.add_argument("--concurrency", type=int, default=8, help="并行院校数")
    parser.add_argument("--years", default="2025-2026")
    parser.add_argument("--colleges-only", action="store_true")
    parser.add_argument("--scores-only", action="store_true")
    args = parser.parse_args()

    py = sys.executable
    common = ["--no-chsi", "--concurrency", str(args.concurrency)]
    if args.offset:
        common.extend(["--offset", str(args.offset)])

    rc = 0

    if not args.scores_only:
        rc = run(
            [py, str(_here / "backfill_colleges_kaoyan.py"), *common],
            "学院补全",
        )
        if rc != 0:
            print(f"学院补全退出码 {rc}", file=sys.stderr)

    if not args.colleges_only:
        crawl_rc = run(
            [
                py,
                str(_here / "crawl_kaoyan_scores_csv.py"),
                "--output",
                str(CSV_OUT),
                "--years",
                args.years,
                *common,
            ],
            "复试线 CSV 抓取",
        )
        if crawl_rc != 0:
            print(f"CSV 抓取退出码 {crawl_rc}", file=sys.stderr)
            sys.exit(crawl_rc)

        import_rc = run(
            [
                py,
                str(_here / "import_kaoyan_scores_batch.py"),
                "--input",
                str(CSV_OUT),
                "--years",
                args.years,
            ],
            "复试线入库",
        )
        if import_rc != 0:
            sys.exit(import_rc)

    run([py, str(_here / "pipeline_enrich.py"), "verify"], "覆盖率报告")

    bump = run([py, str(_here / "notify_frontend.py"), "fast_fill_all"], "通知前端刷新")
    if bump != 0:
        print("notify 失败（可忽略若 migration 006 未应用）", file=sys.stderr)

    print("\n全部完成。", flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
择校 AI 全量补全流水线
============================================================
统一编排：基础信息 → 专业补全 → 学院/复试线 → 后处理 → 清洗 → 覆盖率报告

阶段说明：
  basic    院校基础 + 研招网专业（crawl_basic_once --resume-missing）
  majors   多源 AI 补专业（enrich_majors_ai --popular --thin）
  colleges 掌上考研/研招网学院补全
  import-scores 掌上考研 CSV 分数线导入
  scores   AI 复试线补充（可选）
  dynamic  [已弃用] 研究生院公告抓取，择校模块不再使用
  post     结构化后处理（国家线差、AI 学院）
  cleanup  专业噪声清理（cleanup_majors）
  verify   覆盖率报告

用法：
  python pipeline_enrich.py run --phase all
  python pipeline_enrich.py run --phase dynamic,post --school 清华大学
  python pipeline_enrich.py verify
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("pipeline")

PHASES = (
    "basic",
    "majors",
    "colleges",
    "dynamic",
    "scores",
    "import-scores",
    "post",
    "cleanup",
    "cleanup-project",
    "verify",
)


async def phase_basic(school: Optional[str], force: bool) -> None:
    from crawl_basic_once import main as basic_main

    log.info("═══ Phase 1/6: 基础数据（院校 + 专业目录）═══")
    await basic_main(
        force=force,
        only_school=school,
        majors_only=False,
        resume_missing=not force,
    )


async def phase_majors(
    school: Optional[str],
    thin_limit: int,
    all_schools: bool = False,
) -> None:
    from enrich_majors_ai import main as majors_main

    log.info("═══ Phase 2/6: 专业 AI 补全（聚合站 + 官网深挖）═══")
    if school:
        await majors_main(
            popular=False,
            code=None,
            school=school,
            thin=False,
            thin_limit=0,
            all_schools=False,
        )
        return
    await majors_main(
        popular=True,
        code=None,
        school=None,
        thin=not all_schools,
        thin_limit=thin_limit,
        all_schools=all_schools,
    )


def phase_colleges(school: Optional[str], limit: int, use_chsi: bool) -> None:
    import subprocess

    log.info("═══ Phase: 掌上考研/研招网学院补全 ═══")
    cmd = [sys.executable, str(_here / "backfill_colleges_kaoyan.py")]
    if school:
        cmd.extend(["--school", school])
    if limit > 0:
        cmd.extend(["--limit", str(limit)])
    if not use_chsi:
        cmd.append("--no-chsi")
    subprocess.run(cmd, check=False, cwd=str(_here))


def phase_import_scores(
    school: Optional[str],
    limit: int,
    years: str,
    crawl: bool,
    input_csv: str,
) -> None:
    import subprocess

    log.info("═══ Phase: 掌上考研 CSV 分数线导入 ═══")
    cmd = [
        sys.executable,
        str(_here / "import_kaoyan_scores_csv.py"),
        "--input",
        input_csv,
        "--years",
        years,
    ]
    if crawl:
        cmd.append("--crawl")
    if school:
        cmd.extend(["--school", school])
    if limit > 0:
        cmd.extend(["--limit", str(limit)])
    subprocess.run(cmd, check=False, cwd=str(_here))


async def phase_scores(school: Optional[str], concurrency: int, force: bool) -> None:
    from crawl_scores_ai import main as scores_main

    log.info("═══ Phase: 复试分数线多源抓取 ═══")
    await scores_main(
        concurrency=concurrency,
        only_school=school,
        force=force,
        limit=0,
        detail_limit=10,
        refresh_eol=False,
    )


async def phase_dynamic(
    school: Optional[str],
    concurrency: int,
    deep_pages: int,
) -> None:
    log.warning(
        "dynamic 阶段已弃用（公告模块已移除），跳过 crawl_grad_announcements"
    )


async def phase_post(school: Optional[str], skip_ai_college: bool, college_limit: int) -> None:
    from enrich_postprocess import run_postprocess

    log.info("═══ Phase 4/6: 结构化后处理 ═══")
    await run_postprocess(
        only_school=school,
        skip_ai_college=skip_ai_college,
        college_limit=college_limit,
    )


def phase_cleanup() -> None:
    log.info("═══ Phase 5/6: 专业数据清洗 ═══")
    subprocess.run(
        [sys.executable, str(_here / "cleanup_majors.py")],
        check=False,
        cwd=str(_here),
    )


def phase_cleanup_project(*, files_only: bool = False, db_only: bool = False) -> None:
    log.info("═══ Phase: 项目清理（缓存 + 数据库噪声）═══")
    cmd = [sys.executable, str(_here / "cleanup_project.py")]
    if files_only:
        cmd.append("--files")
    elif db_only:
        cmd.append("--db")
    else:
        cmd.append("--all")
    subprocess.run(cmd, check=False, cwd=str(_here))


def phase_verify() -> None:
    from enrich_postprocess import coverage_report

    log.info("═══ Phase 6/6: 覆盖率报告 ═══")
    coverage_report()


async def run_pipeline(
    phases: list[str],
    school: Optional[str] = None,
    force_basic: bool = False,
    concurrency: int = 2,
    deep_pages: int = 8,
    thin_limit: int = 0,
    skip_ai_college: bool = False,
    college_limit: int = 0,
    all_schools: bool = False,
    college_source_limit: int = 0,
    skip_chsi_college: bool = False,
    import_scores_crawl: bool = False,
    import_scores_limit: int = 0,
    import_scores_years: str = "2025-2026",
    import_scores_csv: str = "",
) -> None:
    start = time.time()
    csv_path = import_scores_csv or str(_here / "data" / "kaoyan_scores_985_211.csv")
    for phase in phases:
        if phase == "basic":
            await phase_basic(school, force_basic)
        elif phase == "majors":
            await phase_majors(school, thin_limit, all_schools=all_schools)
        elif phase == "colleges":
            phase_colleges(school, college_source_limit, use_chsi=not skip_chsi_college)
        elif phase == "dynamic":
            await phase_dynamic(school, concurrency, deep_pages)
        elif phase == "scores":
            await phase_scores(school, concurrency, force=True)
        elif phase == "import-scores":
            phase_import_scores(
                school,
                import_scores_limit,
                import_scores_years,
                import_scores_crawl,
                csv_path,
            )
        elif phase == "post":
            await phase_post(school, skip_ai_college, college_limit)
        elif phase == "cleanup":
            phase_cleanup()
        elif phase == "cleanup-project":
            phase_cleanup_project()
        elif phase == "verify":
            phase_verify()
        else:
            log.warning("未知阶段: %s", phase)

    from notify_frontend import bump_schools_sync

    bump_schools_sync(f"pipeline:{','.join(phases)}")
    log.info("流水线完成，总耗时 %.1fs", time.time() - start)


def parse_phases(raw: str) -> list[str]:
    if raw == "all":
        # 择校核心：院校/专业/学院/复试线（不含公告 dynamic）
        return [p for p in PHASES if p != "dynamic"]
    selected = [p.strip() for p in raw.split(",") if p.strip()]
    bad = [p for p in selected if p not in PHASES]
    if bad:
        raise ValueError(f"无效阶段: {bad}，可选: {', '.join(PHASES)}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="择校 AI 全量补全流水线")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="执行补全流水线")
    run_p.add_argument(
        "--phase",
        default="all",
        help=f"阶段，逗号分隔或 all（默认 all）。可选: {', '.join(PHASES)}",
    )
    run_p.add_argument("--school", default=None, help="仅处理指定院校（模糊匹配）")
    run_p.add_argument("--force-basic", action="store_true", help="基础阶段强制全量重跑")
    run_p.add_argument("--concurrency", type=int, default=3, help="动态/复试线抓取并发院校数")
    run_p.add_argument("--deep-pages", type=int, default=8, help="每校深度详情页数")
    run_p.add_argument("--thin-limit", type=int, default=0, help="专业补全最多处理 N 所薄数据校（0=全部）")
    run_p.add_argument("--all-schools", action="store_true", help="专业阶段对全部 148 校逐校 AI 深挖")
    run_p.add_argument("--skip-ai-college", action="store_true", help="后处理跳过 AI 学院补全")
    run_p.add_argument(
        "--college-limit",
        type=int,
        default=0,
        help="AI 学院补全最多 N 所（0=全部）",
    )
    run_p.add_argument(
        "--college-source-limit",
        type=int,
        default=0,
        help="掌上考研学院补全最多 N 所（0=全部，phase=colleges）",
    )
    run_p.add_argument(
        "--skip-chsi-college",
        action="store_true",
        help="学院补全不访问研招网",
    )
    run_p.add_argument(
        "--import-scores-crawl",
        action="store_true",
        help="import-scores 阶段先抓取 CSV 再导入",
    )
    run_p.add_argument(
        "--import-scores-limit",
        type=int,
        default=0,
        help="import-scores 最多处理 N 所",
    )
    run_p.add_argument(
        "--import-scores-years",
        default="2025-2026",
        help="import-scores 抓取年份范围",
    )
    run_p.add_argument(
        "--import-scores-csv",
        default="",
        help="import-scores CSV 路径（默认 data/kaoyan_scores_985_211.csv）",
    )

    verify_p = sub.add_parser("verify", help="仅输出覆盖率报告")

    args = parser.parse_args()
    if args.cmd == "verify":
        phase_verify()
        return

    phases = parse_phases(args.phase)
    all_schools = args.all_schools or (
        "majors" in phases and args.phase == "all" and not args.school
    )
    asyncio.run(
        run_pipeline(
            phases=phases,
            school=args.school,
            force_basic=args.force_basic,
            concurrency=args.concurrency,
            deep_pages=args.deep_pages,
            thin_limit=args.thin_limit,
            skip_ai_college=args.skip_ai_college,
            college_limit=args.college_limit,
            all_schools=all_schools,
            college_source_limit=args.college_source_limit,
            skip_chsi_college=args.skip_chsi_college,
            import_scores_crawl=args.import_scores_crawl,
            import_scores_limit=args.import_scores_limit,
            import_scores_years=args.import_scores_years,
            import_scores_csv=args.import_scores_csv,
        )
    )


if __name__ == "__main__":
    main()

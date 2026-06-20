"""
Agent 任务执行器 — 将自然语言意图映射到可执行脚本/服务调用。
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from app.config import get_settings

logger = logging.getLogger(__name__)


def resolve_command(intent: str) -> tuple[list[str], str] | None:
    """返回 (argv, description)；无法映射时返回 None（走模拟）。"""
    settings = get_settings()
    root = settings.root
    py = sys.executable
    text = intent.strip()

    sync_script = root / "crawler" / "sync_kaoyan_cn.py"
    updates_script = root / "crawler" / "crawl_updates_smart.py"
    vector_script = root / "backend" / "scripts" / "sync_supabase_vectors.py"

    if "向量" in text or "RAG" in text.upper():
        if vector_script.exists():
            return [py, str(vector_script)], "Supabase → Chroma 向量同步"

    if "招生公告" in text or "公告" in text:
        if updates_script.exists():
            return [py, str(updates_script)], "智能抓取招生公告"

    if "重复专业" in text or "去重" in text:
        return ["__check_duplicates__"], "检查重复专业（数据库查询）"

    if "运营周报" in text or "周报" in text:
        return ["__weekly_report__"], "生成运营周报"

    if "专业" in text or "同步" in text or "985" in text:
        if sync_script.exists():
            args = [py, str(sync_script), "--import-only"]
            uni = _extract_university_name(text)
            if uni:
                args.extend(["--university", uni])
            return args, f"择校数据导入{f'（{uni}）' if uni else ''}"

    return None


def _extract_university_name(text: str) -> str | None:
    m = re.search(r"同步(.{2,12}?)专业", text)
    if m:
        return m.group(1).strip()
    if "浙江大学" in text:
        return "浙江大学"
    if "985" in text:
        return None
    return None


def run_task_subprocess(
    task_id: str,
    argv: list[str],
    on_log: Callable[[str], None],
    on_progress: Callable[[int], None],
    on_done: Callable[[bool, str], None],
) -> None:
    """在后台线程执行命令并回调进度/日志。"""

    def _run() -> None:
        settings = get_settings()
        try:
            if argv[0] == "__check_duplicates__":
                on_log("正在检查 majors 表重复 code…")
                on_progress(40)
                result = _check_duplicate_majors()
                on_log(result)
                on_progress(100)
                on_done(True, "检查完成")
                return

            if argv[0] == "__weekly_report__":
                on_log("正在汇总运营指标…")
                on_progress(50)
                report = _generate_weekly_report()
                on_log(report)
                on_progress(100)
                on_done(True, "周报已生成")
                return

            on_log(f"执行: {' '.join(argv)}")
            on_progress(15)
            proc = subprocess.Popen(
                argv,
                cwd=str(settings.root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert proc.stdout is not None
            lines: list[str] = []
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    lines.append(line)
                    on_log(line[:500])
            code = proc.wait()
            on_progress(100)
            if code == 0:
                on_done(True, "执行成功")
            else:
                on_done(False, f"退出码 {code}")
        except Exception as exc:
            logger.exception("agent task failed")
            on_log(str(exc))
            on_done(False, str(exc))

    threading.Thread(target=_run, daemon=True).start()


def _check_duplicate_majors() -> str:
    settings = get_settings()
    url = settings.effective_supabase_url
    key = settings.effective_supabase_service_key
    if not url or not key:
        return "未配置 Supabase，跳过检查"
    from supabase import create_client

    client = create_client(url, key)
    res = client.table("majors").select("code, university_id").execute()
    rows = res.data or []
    seen: dict[str, int] = {}
    dup = 0
    for row in rows:
        key = f"{row.get('university_id')}:{row.get('code')}"
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            dup += 1
    return f"共 {len(rows)} 条专业，发现 {dup} 组潜在重复"


def _generate_weekly_report() -> str:
    import asyncio

    from app.services import admin_service

    metrics = asyncio.run(admin_service.get_dashboard_metrics())
    return (
        f"运营周报摘要：用户 {metrics.get('usersTotal', 0)}，"
        f"帖子 {metrics.get('postsTotal', 0)}，"
        f"今日新增用户 {metrics.get('usersToday', 0)}，"
        f"今日新增帖子 {metrics.get('postsToday', 0)}"
    )

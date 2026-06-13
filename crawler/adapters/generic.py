"""通用适配器 — 研究生院发现 + 掌上考研复试线兜底。"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from adapters import SchoolAdapter, register_adapter
from discover import fetch_grad_portal_links, is_official_domain
from graduate_urls import resolve_graduate_url

log = logging.getLogger("crawler.adapters.generic")
_ROOT = Path(__file__).resolve().parents[1]


@register_adapter
class GenericAdapter(SchoolAdapter):
    name = "__generic__"

    def discover_urls(self, school: dict[str, Any]) -> list[dict]:
        grad = resolve_graduate_url(school)
        if not grad:
            return []
        links = fetch_grad_portal_links(grad)
        return [l for l in links if is_official_domain(l["url"])]

    def fetch_score_sources(self, school: dict[str, Any], years: list[int]) -> list[dict]:
        """委托现有 fast_fill 复试线管道（掌上考研 CSV）。"""
        return []


def run_legacy_score_pipeline(years: str = "2025-2026", offset: int = 0) -> int:
    """调用既有 fast_fill_all.py 复试线导入。"""
    cmd = [
        sys.executable,
        str(_ROOT / "fast_fill_all.py"),
        "--scores-only",
        "--years",
        years,
    ]
    if offset:
        cmd.extend(["--offset", str(offset)])
    return subprocess.call(cmd, cwd=str(_ROOT))


def run_legacy_college_pipeline(offset: int = 0) -> int:
    cmd = [sys.executable, str(_ROOT / "fast_fill_all.py"), "--colleges-only"]
    if offset:
        cmd.extend(["--offset", str(offset)])
    return subprocess.call(cmd, cwd=str(_ROOT))

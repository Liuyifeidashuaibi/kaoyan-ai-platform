"""清华大学适配器 — 研招网/研究生院复试线页面。"""

from __future__ import annotations

from typing import Any

from adapters import SchoolAdapter, register_adapter
from discover import fetch_grad_portal_links


@register_adapter
class TsinghuaAdapter(SchoolAdapter):
    name = "清华大学"
    slug = "tsinghua"

    def discover_urls(self, school: dict[str, Any]) -> list[dict]:
        grad = school.get("graduate_url") or "https://yz.tsinghua.edu.cn/"
        links = fetch_grad_portal_links(grad)
        extra = [
            {
                "url": "https://yz.tsinghua.edu.cn/",
                "title": "清华大学研究生招生网",
                "page_type": "招生公告",
            }
        ]
        seen = {l["url"] for l in links}
        for e in extra:
            if e["url"] not in seen:
                links.append(e)
        return links

    def fetch_score_sources(self, school: dict[str, Any], years: list[int]) -> list[dict]:
        # 清华复试线多发布于研招网公告，由通用 AI 抽取 + 掌上考研 CSV 兜底
        return []

    def prefer_playwright(self) -> bool:
        return True

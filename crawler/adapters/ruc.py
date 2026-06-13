"""中国人民大学适配器。"""
from __future__ import annotations
from typing import Any
from adapters import SchoolAdapter, register_adapter
from discover import fetch_grad_portal_links

@register_adapter
class RucAdapter(SchoolAdapter):
    name = "中国人民大学"
    slug = "ruc"
    def discover_urls(self, school: dict[str, Any]) -> list[dict]:
        grad = school.get("graduate_url") or "https://pgs.ruc.edu.cn/"
        return fetch_grad_portal_links(grad)
    def fetch_score_sources(self, school: dict[str, Any], years: list[int]) -> list[dict]:
        return []

"""上海交通大学适配器。"""
from __future__ import annotations
from typing import Any
from adapters import SchoolAdapter, register_adapter
from discover import fetch_grad_portal_links

@register_adapter
class SjtuAdapter(SchoolAdapter):
    name = "上海交通大学"
    slug = "sjtu"
    def discover_urls(self, school: dict[str, Any]) -> list[dict]:
        grad = school.get("graduate_url") or "https://yzb.sjtu.edu.cn/"
        return fetch_grad_portal_links(grad)
    def fetch_score_sources(self, school: dict[str, Any], years: list[int]) -> list[dict]:
        return []

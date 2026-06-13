"""学校专属适配器 — 通用框架 + 优先 10 校高质量模板。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

log = logging.getLogger("crawler.adapters")


class SchoolAdapter(ABC):
    """单校抓取适配器基类。"""

    name: str = ""
    slug: str = ""

    @abstractmethod
    def discover_urls(self, school: dict[str, Any]) -> list[dict]:
        """返回 [{url, title, page_type}]"""

    @abstractmethod
    def fetch_score_sources(self, school: dict[str, Any], years: list[int]) -> list[dict]:
        """返回标准化分数行 [{major_code, major, college, year, scores..., source_url}]"""

    def prefer_playwright(self) -> bool:
        return False


# TOP50 热门院校（第一阶段优先抓取）
PRIORITY_SCHOOLS = [
    "清华大学",
    "北京大学",
    "上海交通大学",
    "复旦大学",
    "浙江大学",
    "南京大学",
    "中国科学技术大学",
    "哈尔滨工业大学",
    "武汉大学",
    "华中科技大学",
    "西安交通大学",
    "同济大学",
    "东南大学",
    "中山大学",
    "北京航空航天大学",
    "北京理工大学",
    "电子科技大学",
    "华南理工大学",
    "天津大学",
    "南开大学",
    "中国人民大学",
    "北京师范大学",
    "厦门大学",
    "山东大学",
    "四川大学",
    "吉林大学",
    "中南大学",
    "大连理工大学",
    "西北工业大学",
    "重庆大学",
    "湖南大学",
    "华东师范大学",
    "中国农业大学",
    "东北大学",
    "兰州大学",
    "中国海洋大学",
    "中央民族大学",
    "西北农林科技大学",
    "国防科技大学",
    "北京科技大学",
    "北京邮电大学",
    "上海财经大学",
    "对外经济贸易大学",
    "中央财经大学",
    "苏州大学",
    "南京航空航天大学",
    "南京理工大学",
    "郑州大学",
    "云南大学",
    "新疆大学",
    "中国政法大学",
]

_ADAPTER_REGISTRY: dict[str, type[SchoolAdapter]] = {}


def register_adapter(cls: type[SchoolAdapter]) -> type[SchoolAdapter]:
    _ADAPTER_REGISTRY[cls.name] = cls
    return cls


def get_adapter(school_name: str) -> SchoolAdapter | None:
    cls = _ADAPTER_REGISTRY.get(school_name)
    return cls() if cls else None


def list_adapters() -> list[str]:
    return list(_ADAPTER_REGISTRY.keys())

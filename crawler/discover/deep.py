"""深度页面发现 — 招生栏目 → 复试线等子页。"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from discover import (
    _ANNOUNCE_KEYWORDS,
    _classify_link,
    discover_attachments_from_html,
    discover_links_from_html,
    is_official_domain,
)

_HUB_KEYWORDS = (
    "招生信息",
    "通知公告",
    "硕士招生",
    "研究生招生",
    "招生工作",
    "复试通知",
    "录取公示",
    "公示",
    "硕士",
    "博士",
    "招生",
)

_PRIORITY_PAGE_TYPES = ("复试线", "专业目录", "复试名单")


def discover_hub_links(html: str, base_url: str, *, max_hubs: int = 12) -> list[dict]:
    """发现招生/通知类栏目入口（用于二次抓取）。"""
    soup = BeautifulSoup(html, "lxml")
    hubs: list[dict] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        url = urljoin(base_url, href)
        if url in seen or not is_official_domain(url):
            continue
        title = re.sub(r"\s+", " ", a.get_text(strip=True))[:200]
        if not title:
            continue
        text = f"{title} {url}"
        if not any(k in text for k in _HUB_KEYWORDS):
            continue
        seen.add(url)
        hubs.append({"url": url, "title": title, "page_type": "招生公告", "is_hub": True})
        if len(hubs) >= max_hubs:
            break
    return hubs


def discover_deep_from_portal(
    html: str,
    base_url: str,
    *,
    page_types: Iterable[str] | None = None,
) -> list[dict]:
    """首页 + 栏目页合并发现复试线/复试名单等链接。"""
    types = set(page_types or _PRIORITY_PAGE_TYPES)
    found: list[dict] = []
    seen: set[str] = set()

    def _add(links: list[dict]) -> None:
        for link in links:
            url = link["url"]
            if url in seen:
                continue
            pt = link.get("page_type")
            if pt not in types and not link.get("is_attachment"):
                continue
            seen.add(url)
            found.append(link)

    # 一级：首页直接链接
    for link in discover_links_from_html(html, base_url):
        _add([link])
    for link in discover_attachments_from_html(html, base_url):
        _add([link])

    # 二级：招生栏目列表页
    for hub in discover_hub_links(html, base_url):
        _add([hub])

    return found


def merge_discovered(*batches: list[dict]) -> list[dict]:
    """去重合并多轮发现结果。"""
    out: list[dict] = []
    seen: set[str] = set()
    for batch in batches:
        for link in batch:
            url = link.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(link)
    return out


def same_site(url: str, root_url: str) -> bool:
    """是否同一主域（允许子域）。"""
    a = urlparse(url).netloc.lower().replace("www.", "")
    b = urlparse(root_url).netloc.lower().replace("www.", "")
    if not a or not b:
        return False
    return a == b or a.endswith("." + b) or b.endswith("." + a)

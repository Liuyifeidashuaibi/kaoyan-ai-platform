"""页面发现 — 研究生院/学院/复试线链接发现。"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

_SCORE_KEYWORDS = ("复试", "分数线", "录取分数", "基本分数线", "院线")
_MAJOR_KEYWORDS = ("专业目录", "招生目录", "学科目录")
_ANNOUNCE_KEYWORDS = ("招生简章", "招生公告", "招生信息", "通知公告", "硕士招生")
_ADMISSION_KEYWORDS = (
    "拟录取名单",
    "拟录取公示",
    "统考拟录取名单",
    "研究生拟录取名单",
    "硕士拟录取名单",
    "拟录取考生",
    "录取公示",
)
_RETEST_KEYWORDS = ("复试名单", "复试成绩", "复试通知", "进入复试")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; KaoyanChooseSchoolBot/1.0; +https://kaoyan.ai)"
    ),
}


def discover_links_from_html(
    html: str,
    base_url: str,
    *,
    page_types: Iterable[str] | None = None,
) -> list[dict]:
    """从 HTML 中发现候选来源页。"""
    soup = BeautifulSoup(html, "lxml")
    found: list[dict] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        title = re.sub(r"\s+", " ", a.get_text(strip=True))[:200]
        if not title:
            continue
        page_type = _classify_link(title, url)
        if page_types and page_type not in page_types:
            continue
        if page_type:
            found.append({"url": url, "title": title, "page_type": page_type})

    return found


def _classify_link(title: str, url: str) -> str | None:
    text = f"{title} {url}"
    if any(k in text for k in _ADMISSION_KEYWORDS):
        return "拟录取"
    if any(k in text for k in _RETEST_KEYWORDS):
        return "复试名单"
    if any(k in text for k in _SCORE_KEYWORDS):
        return "复试线"
    if any(k in text for k in _MAJOR_KEYWORDS):
        return "专业目录"
    if any(k in text for k in _ANNOUNCE_KEYWORDS):
        return "招生公告"
    return None


def fetch_grad_portal_links(graduate_url: str, timeout: int = 20) -> list[dict]:
    """抓取研究生院首页并发现子链接（含深度栏目）。"""
    if not graduate_url:
        return []
    try:
        from discover.deep import discover_deep_from_portal
        from fetchers import fetch_page

        html, _ = fetch_page(graduate_url, prefer_playwright=True)
        links = discover_deep_from_portal(html, graduate_url)
        return links
    except Exception:
        return []


def discover_attachments_from_html(html: str, base_url: str) -> list[dict]:
    """从页面中发现 PDF/Excel/Word 附件链接。"""
    soup = BeautifulSoup(html, "lxml")
    found: list[dict] = []
    seen: set[str] = set()
    exts = (".pdf", ".xlsx", ".xls", ".doc", ".docx")

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        lower = url.lower()
        if not any(lower.endswith(ext) for ext in exts):
            continue
        seen.add(url)
        title = re.sub(r"\s+", " ", a.get_text(strip=True))[:200] or url.rsplit("/", 1)[-1]
        page_type = _classify_link(title, url) or "复试线"
        found.append({"url": url, "title": title, "page_type": page_type, "is_attachment": True})
    return found


def is_official_domain(url: str, school_domain_hint: str | None = None) -> bool:
    """过滤非官方域名（论坛/博客）。"""
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    blocked = ("zhihu.com", "weibo.com", "bbs.", "forum.", "blog.", "csdn.net")
    if any(b in host for b in blocked):
        return False
    if school_domain_hint and school_domain_hint not in host:
        return ".edu.cn" in host or ".edu." in host
    return ".edu.cn" in host or ".edu." in host

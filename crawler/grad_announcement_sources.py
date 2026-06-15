"""
研究生院官网：招生公告 / 招生简章 / 调剂 / 推免 采集工具。
从大学官网 + 研究生院主页出发，发现各栏目公告链接并分类。
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from aiohttp import ClientSession

from enrich_constants import TARGET_YEAR
from score_sources import fetch_page_text, grad_announcement_page_urls

# 类型 → 标题匹配关键词
TYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("招生简章", re.compile(r"招生简章|招生章程|硕士招生简章|研究生招生简章")),
    ("调剂信息", re.compile(r"调剂|接收调剂|调剂公告|调剂通知|调剂复试")),
    ("推免公告", re.compile(r"推免|夏令营|预推免|推荐免试|优秀大学生|推免生")),
    ("招生目录", re.compile(r"专业目录|招生目录|招生计划|招生专业目录")),
    ("招生公告", re.compile(r"招生公告|研招公告|招生通知|硕士研究生招生|硕士招生")),
]

ANNOUNCEMENT_TYPES = frozenset(
    {"招生简章", "招生公告", "调剂信息", "推免公告", "招生目录"}
)

# 常见研究生院公告列表路径
GRAD_LIST_PATHS = [
    "/zxgg.htm",
    "/yjszs/tzgg.htm",
    "/yjszs/tzgg/",
    "/yjszs/zsxx/zxgg.htm",
    "/yjszs/zsxx/tzgg.htm",
    "/yjsy/tzgg.htm",
    "/yjsy/news/",
    "/graduate/news/",
    "/graduate/admission/",
    "/info/1024/list.htm",
    "/info/list.htm",
]

_DATE_IN_TITLE = re.compile(r"(20\d{2})[.\-/年](\d{1,2})[.\-/月](\d{1,2})")
_DATE_LINE = re.compile(r"_(\d{1,2})_\s*(20\d{2})\.(\d{1,2})")
_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
_BULLET_LINE_RE = re.compile(
    r"^\s*[\*\-]?\s*_(\d+)_\s*(20\d{2})\.(\d{1,2})\s+(.+?)\s*$"
)
_ANCHOR_TITLE_RE = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*title="([^"]+)"',
    re.I,
)
_ANCHOR_TAG_RE = re.compile(r"<a\s+([^>]+)>(.*?)</a>", re.I | re.S)

# 主页 / 导航里与研招公告相关的关键词
ANNOUNCE_NAV_KEYWORDS = (
    "招生简章", "招生章程", "招生公告", "招生通知", "招生信息", "招生目录",
    "专业目录", "硕士招生", "硕士研究生", "研究生招生", "研招", "招考",
    "调剂", "推免", "夏令营", "预推免", "推荐免试", "复试", "录取",
    "最新公告", "通知公告", "公告", "招生",
)
ANNOUNCE_HREF_HINTS = (
    "zxgg", "tzgg", "zsxx", "yjszs", "sszs", "bszs", "zsgz", "yjsy",
    "graduate", "admission", "notice", "news", "info/list", "/info/",
    "tjxx", "tmgg", "yjszs", "zsjz", "zsml", "zyml",
)
SKIP_HREF_HINTS = (
    "javascript:", "mailto:", "#", ".css", ".js", ".jpg", ".png", ".pdf",
    "login", "register", "english", "/en/", "recruit", "job", "zp.", "rczp",
    "bkzs", "本科招生", "就业", "校友", "图书馆", "邮箱", "vpn",
)


def _base_domain(host: str) -> str:
    parts = (host or "").lower().split(".")
    if len(parts) >= 3 and parts[-2] in ("edu", "gov", "com", "cn", "org"):
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host or ""


def _related_site(url: str, website: str, grad_url: str) -> bool:
    if not url.startswith("http"):
        return False
    link_host = urlparse(url).netloc.lower()
    if not link_host:
        return False
    link_base = _base_domain(link_host)
    for seed in (website, grad_url):
        if not seed:
            continue
        seed_host = urlparse(seed).netloc.lower()
        if link_host == seed_host:
            return True
        if _base_domain(seed_host) == link_base:
            return True
        if any(p in link_host for p in ("gs.", "grs.", "yjs", "yz.", "graduate", "admission")):
            return True
    return False


def _normalize_discovered_url(href: str, base_url: str) -> str:
    href = (href or "").strip().split("#")[0].split("?")[0].strip()
    parts = href.strip("\"'").split()
    if not parts:
        return ""
    href = parts[0]
    if not href:
        return ""
    low = href.lower()
    if any(low.startswith(x) or x in low for x in SKIP_HREF_HINTS):
        return ""
    if not href.startswith("http"):
        href = urljoin(base_url, href)
        low = href.lower()
        if any(x in low for x in SKIP_HREF_HINTS):
            return ""
    if " " in href or '"' in href:
        return ""
    return href


def _is_announcement_nav(href: str, title: str) -> bool:
    blob = f"{title} {href}".lower()
    if any(k.lower() in blob for k in ANNOUNCE_NAV_KEYWORDS):
        return True
    if any(h in blob for h in ANNOUNCE_HREF_HINTS):
        return True
    return False


def _is_likely_list_page(url: str) -> bool:
    low = url.lower()
    if re.search(r"/info/\d+/\d+\.htm", low):
        return False
    if any(h in low for h in ("list", "zxgg", "tzgg", "notice", "news", "gg", "index.htm")):
        return True
    if low.endswith((".htm", ".html", ".shtml", "/")):
        return True
    return False


def extract_html_anchor_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """从 HTML 提取 (href, title)。"""
    out: list[tuple[str, str]] = []
    if not html:
        return out
    for href, title in _ANCHOR_TITLE_RE.findall(html):
        href = _normalize_discovered_url(href, base_url)
        if href:
            out.append((href, _clean_title(title)))
    for attrs, inner in _ANCHOR_TAG_RE.findall(html):
        href_m = re.search(r"""href=["']([^"']+)["']""", attrs, re.I)
        if not href_m:
            continue
        href = _normalize_discovered_url(href_m.group(1), base_url)
        if not href:
            continue
        title_m = re.search(r"""title=["']([^"']+)["']""", attrs, re.I)
        if title_m:
            title = _clean_title(title_m.group(1))
        else:
            title = _clean_title(re.sub(r"<[^>]+>", "", inner))
        if title:
            out.append((href, title))
    return out


def discover_announcement_urls_from_html(
    html: str,
    base_url: str,
    website: str = "",
    grad_url: str = "",
    include_articles: bool = True,
) -> list[str]:
    """从主页/列表页 HTML 发现公告栏目与文章链接。"""
    urls: list[str] = []
    for href, title in extract_html_anchor_links(html, base_url):
        if not _related_site(href, website, grad_url or base_url):
            continue
        if _is_announcement_nav(href, title):
            urls.append(href)
            continue
        if include_articles and classify_announcement_title(title):
            if href.endswith((".htm", ".html", ".shtml")) or "/info/" in href:
                urls.append(href)
    return _dedupe_urls(urls)


def discover_announcement_urls_from_markdown(
    md: str,
    base_url: str,
    website: str = "",
    grad_url: str = "",
) -> list[str]:
    urls: list[str] = []
    for title, href in _LINK_RE.findall(md or ""):
        href = _normalize_discovered_url(href, base_url)
        if not href or not _related_site(href, website, grad_url or base_url):
            continue
        if _is_announcement_nav(href, title) or classify_announcement_title(title):
            urls.append(href)
    return _dedupe_urls(urls)


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        key = u.rstrip("/").lower()
        if key not in seen:
            seen.add(key)
            out.append(u)
    return out


def prioritize_announcement_urls(urls: list[str]) -> list[str]:
    def rank(u: str) -> int:
        low = u.lower()
        score = 0
        for i, frag in enumerate((
            "zxgg", "tzgg", "yjszs", "zsxx", "sszs", "调剂", "推免",
            "招生简章", "招生章程", "info/list", "/info/",
        )):
            if frag in low:
                score += 30 - i
        if _is_likely_list_page(u):
            score += 10
        return score

    return sorted(urls, key=rank, reverse=True)


async def discover_site_announcement_urls(
    session: ClientSession,
    website: str,
    grad_url: Optional[str],
) -> list[str]:
    """从大学官网 + 研究生院主页抓取并发现公告相关链接。"""
    from crawl_basic_once import guess_grad_subdomains

    seeds: list[str] = []
    if grad_url and grad_url.startswith("http"):
        seeds.append(grad_url.rstrip("/") + "/")
    if website and website.startswith("http"):
        seeds.append(website.rstrip("/") + "/")
    if not grad_url and website:
        for g in guess_grad_subdomains(website)[:2]:
            seeds.append(g.rstrip("/") + "/")

    discovered: list[str] = []
    seen_pages: set[str] = set()
    for page_url in _dedupe_urls(seeds)[:4]:
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)
        html = None
        try:
            from crawl_updates_smart import http_get

            html = await http_get(session, page_url)
        except Exception:
            pass
        if html:
            discovered.extend(
                discover_announcement_urls_from_html(
                    html, page_url, website, grad_url or page_url
                )
            )
        try:
            md = await fetch_page_text(session, page_url)
            if md:
                discovered.extend(
                    discover_announcement_urls_from_markdown(
                        md, page_url, website, grad_url or page_url
                    )
                )
        except Exception:
            pass

    return prioritize_announcement_urls(_dedupe_urls(discovered))


def _recruitment_years(base: int = TARGET_YEAR) -> set[int]:
    return {base, base + 1}


def classify_announcement_title(title: str) -> Optional[str]:
    t = (title or "").strip()
    if len(t) < 4:
        return None
    for dtype, pat in TYPE_PATTERNS:
        if pat.search(t):
            return dtype
    if re.search(r"推免|夏令营|预推免|推荐免试", t):
        return "推免公告"
    if re.search(r"调剂", t):
        return "调剂信息"
    if re.search(r"招生简章|招生章程", t):
        return "招生简章"
    if re.search(r"专业目录|招生目录|招生计划", t):
        return "招生目录"
    if re.search(r"硕士|博士|研究生|招生|复试|录取|考点|报名|初试", t):
        return "招生公告"
    return None


def _parse_publish_time(title: str, context: str = "") -> Optional[str]:
    for text in (title, context):
        m = _DATE_IN_TITLE.search(text)
        if m:
            y, mo, d = m.groups()
            return f"{y}-{int(mo):02d}-{int(d):02d}"
        m2 = _DATE_LINE.search(text)
        if m2:
            _, y, mo = m2.groups()
            return f"{y}-{int(mo):02d}-01"
    return None


def is_target_year(title: str, publish_time: Optional[str], year: int = TARGET_YEAR) -> bool:
    years = _recruitment_years(year)
    for y in years:
        ys = str(y)
        if ys in title:
            return True
        if publish_time and publish_time.startswith(ys):
            return True
    if publish_time:
        py = int(publish_time[:4]) if publish_time[:4].isdigit() else None
        if py is not None and py in years:
            return True
    return False


def _recruitment_year(
    title: str,
    publish_time: Optional[str],
    default: int = TARGET_YEAR,
) -> int:
    for text in (title, publish_time or ""):
        m = re.search(r"(20\d{2})", text)
        if m:
            y = int(m.group(1))
            if y in _recruitment_years(default):
                return y
    return default


def _same_host(base: str, link: str) -> bool:
    try:
        return urlparse(base).netloc == urlparse(link).netloc
    except Exception:
        return False


def _portal_base(url: str) -> str:
    """归一为研究生院门户根，避免在文章详情页后拼接 zxgg 路径。"""
    if not url or not url.startswith("http"):
        return url or ""
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    if re.search(r"/info/\d+/\d+\.htm", path):
        return f"{parsed.scheme}://{parsed.netloc}"
    if path.count("/") > 2 and not any(
        k in path for k in ("zxgg", "tzgg", "list", "index.htm", "yjszs", "zsxx")
    ):
        return f"{parsed.scheme}://{parsed.netloc}"
    return url.rstrip("/")


def build_grad_announcement_urls(
    website: str,
    grad_url: Optional[str],
    discovered: Optional[list[str]] = None,
) -> list[str]:
    """汇总研究生院公告候选 URL：主页发现 + 常见路径 + 分页。"""
    seen: set[str] = set()
    urls: list[str] = []

    def _add(u: str) -> None:
        u = (u or "").strip()
        if u.startswith("http") and u not in seen:
            seen.add(u)
            urls.append(u)

    for u in discovered or []:
        _add(u)

    portal = _portal_base(grad_url or "")
    if portal.startswith("http"):
        _add(portal)
        for u in grad_announcement_page_urls(portal):
            _add(u)
        if not discovered:
            for path in GRAD_LIST_PATHS:
                _add(f"{portal.rstrip('/')}{path}")

    base = (website or "").rstrip("/")
    if base and not discovered:
        _add(base)
        for path in GRAD_LIST_PATHS:
            _add(f"{base}{path}")
    elif base and discovered:
        _add(base)

    return prioritize_announcement_urls(urls)


def _clean_title(title: str) -> str:
    t = (title or "").strip()
    t = re.sub(r"^_\d+_\s*", "", t)
    t = re.sub(r"^20\d{2}[.\-/年]\d{1,2}[.\-/月]?\d{0,2}\s*", "", t)
    return t.strip()[:200]


def _append_list_item(
    items: list[dict],
    seen: set[str],
    title: str,
    href: str,
    source_url: str,
    year: int,
    pub: Optional[str],
    limit: int,
) -> bool:
    title = _clean_title(title)
    if len(title) < 6 or title in seen:
        return False
    dtype = classify_announcement_title(title)
    if not dtype:
        return False
    if not is_target_year(title, pub, year):
        return False
    href = (href or "").strip().split('"')[0].split("?")[0].strip()
    if href and not href.startswith("http"):
        href = urljoin(source_url, href)
    if href and not _same_host(source_url, href) and "chsi.com.cn" not in href:
        grad_host = urlparse(source_url).netloc
        if grad_host and urlparse(href).netloc and urlparse(href).netloc != grad_host:
            if dtype not in ("调剂信息", "推免公告"):
                return False
    seen.add(title)
    items.append({
        "type": dtype,
        "title": title[:200],
        "link": href,
        "publish_time": pub or f"{year}-01-01",
        "content": "",
        "year": _recruitment_year(title, pub, year),
    })
    return len(items) >= limit


def parse_list_html_items(
    html: str,
    source_url: str,
    year: int = TARGET_YEAR,
    limit: int = 80,
) -> list[dict]:
    """从 HTML 列表页提取条目（title 属性 + 链接文字）。"""
    items: list[dict] = []
    seen: set[str] = set()
    if not html:
        return items
    for href, title in extract_html_anchor_links(html, source_url):
        pub = _parse_publish_time(title)
        if _append_list_item(items, seen, title, href, source_url, year, pub, limit):
            return items
    return items


def parse_bullet_list_items(
    content: str,
    source_url: str,
    year: int = TARGET_YEAR,
    limit: int = 80,
) -> list[dict]:
    """Jina 纯文本列表（无 Markdown 链接）。"""
    items: list[dict] = []
    seen: set[str] = set()
    for line in content.splitlines():
        m = _BULLET_LINE_RE.match(line.strip())
        if not m:
            continue
        _, y, mo, title = m.groups()
        pub = f"{y}-{int(mo):02d}-01"
        if _append_list_item(items, seen, title, "", source_url, year, pub, limit):
            return items
    return items


def merge_announcement_items(*groups: list[dict]) -> list[dict]:
    """按标题去重，优先保留带 link 的条目。"""
    by_title: dict[str, dict] = {}
    for group in groups:
        for it in group:
            title = str(it.get("title") or "").strip()
            if not title:
                continue
            prev = by_title.get(title)
            if prev is None or (not prev.get("link") and it.get("link")):
                by_title[title] = it
    return list(by_title.values())


def parse_list_page_items(
    content: str,
    source_url: str,
    year: int = TARGET_YEAR,
    limit: int = 80,
) -> list[dict]:
    """从公告列表页 Markdown 提取结构化条目（无需 AI）。"""
    items: list[dict] = []
    seen: set[str] = set()
    lines = content.splitlines()

    for i, line in enumerate(lines):
        for title, href in _LINK_RE.findall(line):
            ctx = "\n".join(lines[max(0, i - 2) : i + 3])
            pub = _parse_publish_time(title, ctx)
            if _append_list_item(items, seen, title, href, source_url, year, pub, limit):
                return items

    return items


def parse_grad_list_page(
    content: str,
    html: Optional[str],
    source_url: str,
    year: int = TARGET_YEAR,
    limit: int = 80,
) -> list[dict]:
    """Markdown + HTML + 纯文本列表联合解析。"""
    md_items = parse_list_page_items(content, source_url, year, limit)
    html_items = parse_list_html_items(html or "", source_url, year, limit)
    bullet_items = parse_bullet_list_items(content, source_url, year, limit)
    return merge_announcement_items(html_items, md_items, bullet_items)[:limit]


def item_from_detail_page(
    detail_text: str,
    seed: dict,
    year: int = TARGET_YEAR,
) -> dict:
    """用详情页正文补充 content 摘要。"""
    body = re.sub(r"\s+", " ", detail_text).strip()
    for marker in ("Markdown Content:", "URL Source:", "Title:"):
        if marker in body:
            body = body.split(marker, 1)[-1]
    summary = body[:500].strip()
    item = dict(seed)
    item["content"] = summary[:120] if summary else item.get("content", "")
    title = str(item.get("title") or "")
    pub = item.get("publish_time") or _parse_publish_time(title, body)
    item["year"] = _recruitment_year(title, pub, year)
    if not item.get("publish_time"):
        item["publish_time"] = pub or f"{year}-01-01"
    return item


async def fetch_detail_items(
    session: ClientSession,
    seeds: list[dict],
    year: int = TARGET_YEAR,
) -> list[dict]:
    """抓取详情页并补全正文摘要。"""
    out: list[dict] = []
    for seed in seeds:
        link = str(seed.get("link") or "").strip()
        if not link.startswith("http"):
            out.append(seed)
            continue
        text = await fetch_page_text(session, link)
        if text and len(text) > 150:
            out.append(item_from_detail_page(text, seed, year))
        else:
            out.append(seed)
    return out

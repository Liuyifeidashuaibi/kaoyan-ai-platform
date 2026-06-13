"""
多源复试分数线采集：中国教育在线（EOL）+ 页面结构化解析。
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from crawl_updates_smart import jina_fetch, http_get, MAX_CHARS
from enrich_constants import TARGET_YEAR, national_line_for_major
from enrich_majors_ai import _normalize_name, _strip_paren

log = logging.getLogger("score_sources")

EOL_2024_INDEX = "https://kaoyan.eol.cn/nnews/202404/t20240401_2593332.shtml"
EOL_SCORE_LIST_PAGES = [
    "https://kaoyan.eol.cn/tiao_ji/wang_nian_fen_shu/index.shtml",
    "https://kaoyan.eol.cn/tiao_ji/wang_nian_fen_shu/index_1.shtml",
    "https://kaoyan.eol.cn/tiao_ji/wang_nian_fen_shu/index_2.shtml",
]
CACHE_DIR = Path(__file__).parent / "data"
EOL_INDEX_CACHE = CACHE_DIR / "eol_score_index.json"
EOL_LIST_CACHE = CACHE_DIR / "eol_score_list_articles.json"

_SLASH_RE = re.compile(
    r"(?<![\d.])(\d{2,3})/(\d{2,3})/(\d{2,3})/(\d{2,3})/(\d{2,3})(?![\d.])"
)
_CODE_RE = re.compile(r"(0\d{5})")
_URL_RE = re.compile(r"https?://[^\s\|，,<>\"')]+")
_NATIONAL_KW = re.compile(r"国家\s*[AＡaａ]?\s*区?线|执行国家线|国家线")
_BASIC_LINE_FULL = re.compile(
    r"(?:学术学位|专业学位)\s+(\d{2,6})\s+.+?\s+"
    r"(\d{2,3})\s+(\d{2,3})\s+(\d{2,3})\s+(\d{2,3})\s+(\d{2,3})"
)
_BASIC_LINE_SHORT = re.compile(
    r"(?:学术学位|专业学位)\s+(\d{2,6})\s+.+?\s+"
    r"(\d{2,3})\s+(\d{2,3})\s+(\d{2,3})(?:\s|$)"
)
_SCORE_LINK_KW = ("复试", "分数线", "录取线", "基本线", "fsx", "报录比")
_INDEX_LONG_CHARS = 55_000


async def jina_fetch_long(
    session: ClientSession,
    url: str,
    max_chars: int = _INDEX_LONG_CHARS,
) -> str:
    """长文页面（如 EOL 593 校索引）专用 Jina 抓取。"""
    from crawl_updates_smart import JINA_BASE, USER_AGENTS
    import random

    try:
        async with session.get(
            f"{JINA_BASE}{url}",
            headers={
                "Accept": "text/plain",
                "X-Timeout": "40",
                "User-Agent": random.choice(USER_AGENTS),
            },
            timeout=__import__("aiohttp").ClientTimeout(total=70),
        ) as resp:
            if resp.status == 200:
                return (await resp.text())[:max_chars]
    except Exception as exc:
        log.debug("Jina long %s: %s", url[-60:], exc)
    return ""


def _split_urls_from_line(line: str) -> list[str]:
    urls: list[str] = []
    for chunk in re.split(r"[；;，,]\s*", line):
        for u in _URL_RE.findall(chunk):
            u = u.rstrip(")").rstrip("。").rstrip("，").rstrip("；")
            if u.startswith("http"):
                urls.append(u)
    return urls


def _normalize_url(url: str) -> str:
    u = (url or "").strip()
    if "search/index" in u or "searchKey=" in u:
        return u
    return u.split("?")[0]


def is_valid_crawl_url(url: str) -> bool:
    """过滤中文标题误当 URL、超长/含空格等脏链接。"""
    u = (url or "").strip()
    if not u.startswith("http"):
        return False
    if " " in u or len(u) > 480:
        return False
    # UTF-8 中文被 percent-encode 后常见于错误链接
    if re.search(r"%[89A-F][0-9A-F]{2}", u[:120], re.I):
        return False
    return True


def expand_school_line_items(
    items: list[dict],
    major_map: dict[str, str],
) -> list[dict]:
    """校线 PDF 常为 2/4 位代码，展开为本校 6 位专业代码。"""
    out: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for item in items:
        digits = re.sub(r"\D", "", str(item.get("major_code") or ""))
        targets: list[str] = []
        if len(digits) >= 6 and digits[:6] in major_map:
            targets = [digits[:6]]
        elif len(digits) >= 4:
            targets = sorted(c for c in major_map if c.startswith(digits[:4]))
        elif len(digits) >= 2:
            targets = sorted(c for c in major_map if c.startswith(digits[:2]))
        for code in targets:
            key = (code, int(item.get("total_score") or 0))
            if key in seen:
                continue
            seen.add(key)
            row = dict(item)
            row["major_code"] = code
            out.append(row)
    return out


def parse_school_basic_lines(content: str, year: int = TARGET_YEAR) -> list[dict]:
    """解析研究生院 PDF/HTML 中的校复试基本分数线表格。"""
    items: list[dict] = []
    seen: set[str] = set()
    flat = re.sub(r"\s+", " ", content)

    for m in _BASIC_LINE_FULL.finditer(flat):
        code, p, e, p1, p2, total = m.groups()
        if code in seen or not total.isdigit():
            continue
        total_i = int(total)
        if total_i < 140 or total_i > 510:
            continue
        seen.add(code)
        items.append({
            "type": "复试分数线",
            "year": year,
            "major_code": code,
            "politics_score": int(p),
            "english_score": int(e),
            "professional1_score": int(p1),
            "professional2_score": int(p2),
            "total_score": total_i,
            "title": m.group(0)[:120],
        })

    for m in _BASIC_LINE_SHORT.finditer(flat):
        code, p, e, total = m.groups()
        if code in seen:
            continue
        total_i = int(total)
        if total_i < 140 or total_i > 510:
            continue
        seen.add(code)
        items.append({
            "type": "复试分数线",
            "year": year,
            "major_code": code,
            "politics_score": int(p),
            "english_score": int(e),
            "total_score": total_i,
            "title": m.group(0)[:120],
        })
    return items


def _clean_href(href: str) -> str:
    return href.strip().split('"')[0].split("'")[0].rstrip(")").rstrip("，").strip()


def grad_announcement_page_urls(grad_url: Optional[str]) -> list[str]:
    """研究生院公告列表分页（2025 复试线常在第 5+ 页）。"""
    if not grad_url or not grad_url.startswith("http"):
        return []
    gbase = grad_url.rstrip("/")
    urls = [f"{gbase}/zxgg.htm"]
    urls.extend(f"{gbase}/zxgg/{i}.htm" for i in range(2, 16))
    return urls


def discover_score_links(
    content: str,
    source_url: str,
    year: int = TARGET_YEAR,
    limit: int = 12,
    html: Optional[str] = None,
) -> list[str]:
    """从公告页发现复试线正文 / PDF 附件链接。"""
    urls: list[str] = []
    seen: set[str] = {_normalize_url(source_url)}
    year_s = str(year)
    score_kw = _SCORE_LINK_KW + ("分数线", "基本线", "校线", "院线")

    def _maybe_add(href: str, title: str) -> bool:
        href = _clean_href(href)
        if not is_valid_crawl_url(href):
            return False
        if year_s not in title and year_s not in href:
            if ".pdf" not in href.lower():
                return False
        if not any(kw in title for kw in score_kw):
            if ".pdf" not in href.lower():
                return False
        norm = _normalize_url(href)
        if norm in seen:
            return False
        seen.add(norm)
        urls.append(href)
        return len(urls) >= limit

    for title, href in re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", content):
        _maybe_add(href, title)
        if len(urls) >= limit:
            return urls

    if html:
        try:
            from grad_announcement_sources import extract_html_anchor_links
            for href, title in extract_html_anchor_links(html, source_url):
                _maybe_add(href, title)
                if len(urls) >= limit:
                    return urls
        except Exception as exc:
            log.debug("HTML score links %s: %s", source_url[-40:], exc)

    for href in _URL_RE.findall(content):
        href = _clean_href(href)
        if ".pdf" not in href.lower():
            continue
        if year_s not in href and "复试" not in href:
            continue
        norm = _normalize_url(href)
        if norm not in seen:
            seen.add(norm)
            urls.append(href)
        if len(urls) >= limit:
            break
    return urls



def html_to_text(html: str) -> str:
    if not html or len(html) < 80:
        return ""
    try:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text("\n", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


async def fetch_page_text(session: ClientSession, url: str) -> str:
    """Jina Reader 优先，失败则 HTTP + HTML 转文本。"""
    text = await jina_fetch(session, url)
    if text and len(text) >= 150:
        return text[:MAX_CHARS]
    raw = await http_get(session, url)
    if not raw:
        return ""
    if raw.lstrip().startswith("%PDF") or "application/pdf" in raw[:200].lower():
        pdf_text = await jina_fetch(session, url)
        return (pdf_text or "")[:MAX_CHARS]
    plain = html_to_text(raw)
    if len(plain) >= 150:
        return plain[:MAX_CHARS]
    return raw[:MAX_CHARS]


def parse_eol_index_text(text: str) -> dict[str, list[str]]:
    """解析 EOL 593 校汇总文：序号、校名、URL。"""
    schools: dict[str, list[str]] = {}
    current: Optional[str] = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d+)[、,.．](.+)$", line)
        if m:
            current = _strip_paren(m.group(2).strip())
            schools.setdefault(current, [])
            continue
        if current:
            for u in _split_urls_from_line(line):
                if u not in schools[current]:
                    schools[current].append(u)
    return schools


def find_eol_urls(school_name: str, index: dict[str, list[str]]) -> list[str]:
    """按校名在 EOL 索引中查找 URL。"""
    if not index:
        return []

    def _flat(urls: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for u in urls:
            for part in _split_urls_from_line(u):
                if part not in seen:
                    seen.add(part)
                    out.append(part)
        return out

    raw = school_name.strip()
    stripped = _strip_paren(raw)
    norm = _normalize_name(stripped)

    if raw in index:
        return _flat(index[raw])
    if stripped in index:
        return _flat(index[stripped])

    for key, urls in index.items():
        kn = _normalize_name(_strip_paren(key))
        if kn == norm:
            return _flat(urls)

    best: list[str] = []
    best_len = 0
    for key, urls in index.items():
        kn = _normalize_name(_strip_paren(key))
        if norm.startswith(kn) or kn.startswith(norm):
            overlap = min(len(norm), len(kn))
            if overlap > best_len:
                best_len = overlap
                best = list(urls)
    return _flat(best)


def parse_eol_list_articles(
    text: str,
    school_name: str,
    year: int = TARGET_YEAR,
) -> list[str]:
    """从 EOL 复试线列表页提取与该校相关的文章链接。"""
    short = _strip_paren(school_name)
    tokens = [short, short[:4] if len(short) >= 4 else short[:2]]
    urls: list[str] = []
    seen: set[str] = set()
    year_s = str(year)

    for title, href in re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", text):
        if year_s not in title:
            continue
        if not any(kw in title for kw in ("复试", "分数线", "录取线", "基本线")):
            continue
        if not any(tok in title for tok in tokens if tok):
            continue
        href = href.split("?")[0]
        if href not in seen:
            seen.add(href)
            urls.append(href)

    for m in re.finditer(
        rf"({re.escape(short)}[^\n]{{0,40}}{year_s}[^\n]{{0,40}}(?:复试|分数线)[^\n]*)\n+(https?://\S+)",
        text,
    ):
        href = m.group(2).rstrip(")").split("?")[0]
        if href not in seen:
            seen.add(href)
            urls.append(href)

    return urls


def eol_search_url(school_name: str, year: int = TARGET_YEAR) -> str:
    q = quote(f"{_strip_paren(school_name)}{year}年硕士研究生复试分数线")
    return f"https://kaoyan.eol.cn/search/index.shtml?searchKey={q}"


def parse_eol_search_results(text: str, school_name: str, year: int = TARGET_YEAR) -> list[str]:
    short = _strip_paren(school_name)
    year_s = str(year)
    urls: list[str] = []
    seen: set[str] = set()
    for title, href in re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", text):
        if year_s not in title and "复试" not in title:
            continue
        if short[:2] not in title and short not in title:
            continue
        href = href.split("?")[0]
        if "eol.cn" in href and href not in seen:
            seen.add(href)
            urls.append(href)
    return urls


def parse_slash_scores(content: str, year: int = TARGET_YEAR) -> list[dict]:
    """解析 政治/英语/业务一/业务二/总分 五段式复试线。"""
    items: list[dict] = []
    seen: set[str] = set()
    for line in content.splitlines():
        if not _CODE_RE.search(line):
            continue
        slash = _SLASH_RE.search(line)
        if not slash:
            continue
        code = _CODE_RE.search(line).group(1)
        if code in seen:
            continue
        politics, english, pro1, pro2, total = (int(x) for x in slash.groups())
        if total < 140 or total > 510:
            continue
        seen.add(code)
        items.append({
            "type": "复试分数线",
            "year": year,
            "major_code": code,
            "politics_score": politics,
            "english_score": english,
            "professional1_score": pro1,
            "professional2_score": pro2,
            "total_score": total,
            "title": line[:120],
        })
    return items


def parse_national_line_scores(
    content: str,
    year: int,
    category_by_code: dict[str, str],
    degree_by_code: dict[str, str],
) -> list[dict]:
    """EOL 报录比表中「国家A线」行 → 用国家线总分入库。"""
    items: list[dict] = []
    seen: set[str] = set()
    for line in content.splitlines():
        if not _CODE_RE.search(line):
            continue
        if not _NATIONAL_KW.search(line):
            continue
        code = _CODE_RE.search(line).group(1)
        if code in seen:
            continue
        total = national_line_for_major(
            code,
            category_by_code.get(code),
            degree_by_code.get(code),
        )
        if not total or total < 140:
            continue
        seen.add(code)
        items.append({
            "type": "复试分数线",
            "year": year,
            "major_code": code,
            "total_score": total,
            "politics_score": 0,
            "english_score": 0,
            "title": line[:120],
        })
    return items


def parse_structured_scores(
    content: str,
    year: int = TARGET_YEAR,
    category_by_code: Optional[dict[str, str]] = None,
    degree_by_code: Optional[dict[str, str]] = None,
) -> list[dict]:
    """合并结构化解析（五段式 + 国家线 + 校线 PDF），不调用 AI。"""
    cat = category_by_code or {}
    deg = degree_by_code or {}
    merged: dict[str, dict] = {}
    for item in (
        parse_slash_scores(content, year)
        + parse_school_basic_lines(content, year)
        + parse_national_line_scores(content, year, cat, deg)
    ):
        merged[item["major_code"]] = item
    return list(merged.values())


def _load_json_cache(path: Path) -> Optional[dict | list]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_json_cache(path: Path, data: object) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def load_eol_index(session: ClientSession, force: bool = False) -> dict[str, list[str]]:
    cached = None if force else _load_json_cache(EOL_INDEX_CACHE)
    if isinstance(cached, dict) and cached:
        log.info("EOL 索引缓存 %d 校", len(cached))
        return cached

    log.info("拉取 EOL 593 校复试线索引…")
    text = await jina_fetch_long(session, EOL_2024_INDEX)
    if len(text) < 5000:
        text = await fetch_page_text(session, EOL_2024_INDEX)
    if not text:
        log.warning("EOL 索引页抓取失败")
        return {}
    index = parse_eol_index_text(text)
    if index:
        _save_json_cache(EOL_INDEX_CACHE, index)
        log.info("EOL 索引解析 %d 校", len(index))
    return index


async def load_eol_list_articles(
    session: ClientSession,
    force: bool = False,
) -> list[dict]:
    cached = None if force else _load_json_cache(EOL_LIST_CACHE)
    if isinstance(cached, list) and cached:
        return cached

    articles: list[dict] = []
    for page_url in EOL_SCORE_LIST_PAGES:
        text = await fetch_page_text(session, page_url)
        if not text:
            continue
        for title, href in re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", text):
            if not re.search(r"20\d{2}", title):
                continue
            if not any(kw in title for kw in ("复试", "分数线", "录取线", "基本线", "报录比")):
                continue
            articles.append({"title": title.strip(), "url": href.split("?")[0]})

    if articles:
        _save_json_cache(EOL_LIST_CACHE, articles)
        log.info("EOL 列表页缓存 %d 篇", len(articles))
    return articles


def articles_for_school(
    articles: list[dict],
    school_name: str,
    year: int = TARGET_YEAR,
) -> list[str]:
    short = _strip_paren(school_name)
    year_s = str(year)
    urls: list[str] = []
    seen: set[str] = set()
    for row in articles:
        title = row.get("title") or ""
        if year_s not in title:
            continue
        if short[:2] not in title and short not in title:
            continue
        url = str(row.get("url") or "").split("?")[0]
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def collect_score_urls_tiered(
    school_name: str,
    website: str,
    grad_url: Optional[str],
    school_code: Optional[str],
    eol_index: dict[str, list[str]],
    eol_articles: list[dict],
    year: int = TARGET_YEAR,
) -> dict[str, list[str]]:
    """按优先级分层：EOL 文章/索引 → 站内搜索 → 研究生院公告 → 路径猜测。"""
    from crawl_updates_smart import build_score_urls

    seen: set[str] = set()

    def _add_many(raw: list[str], limit: int = 0) -> list[str]:
        out: list[str] = []
        for u in raw:
            u = (u or "").strip()
            if not is_valid_crawl_url(u):
                continue
            norm = _normalize_url(u)
            if norm in seen:
                continue
            seen.add(norm)
            out.append(u)
            if limit and len(out) >= limit:
                break
        return out

    eol: list[str] = []
    for u in articles_for_school(eol_articles, school_name, year):
        eol.extend(_add_many([u]))
    for u in find_eol_urls(school_name, eol_index):
        eol.extend(_add_many([u]))

    search = _add_many([eol_search_url(school_name, year)], limit=1)
    grad = _add_many(grad_announcement_page_urls(grad_url)[:6], limit=6)
    guess = _add_many(build_score_urls(website, grad_url, school_name, school_code), limit=8)

    return {"eol": eol, "search": search, "grad": grad, "guess": guess}


async def collect_score_urls_for_school(
    session: ClientSession,
    school_name: str,
    website: str,
    grad_url: Optional[str],
    school_code: Optional[str],
    eol_index: dict[str, list[str]],
    eol_articles: list[dict],
    year: int = TARGET_YEAR,
) -> list[str]:
    """汇总该校复试线候选 URL（EOL 优先，扁平列表）。"""
    tiers = collect_score_urls_tiered(
        school_name, website, grad_url, school_code, eol_index, eol_articles, year,
    )
    flat: list[str] = []
    for key in ("eol", "search", "grad", "guess"):
        flat.extend(tiers.get(key) or [])
    return flat


def get_major_meta_maps(
    db,
    university_id: str,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """code → major_id；code → subject_category；code → degree_type"""
    try:
        res = (
            db._sb.table("majors")
            .select("id,code,subject_category,degree_type")
            .eq("university_id", university_id)
            .execute()
        )
    except Exception as exc:
        log.error("get_major_meta: %s", exc)
        return {}, {}, {}

    major_map: dict[str, str] = {}
    cat_map: dict[str, str] = {}
    deg_map: dict[str, str] = {}
    for row in res.data or []:
        code = re.sub(r"\D", "", str(row.get("code") or ""))[:6]
        if len(code) != 6:
            continue
        major_map[code] = row["id"]
        if row.get("subject_category"):
            cat_map[code] = str(row["subject_category"])
        if row.get("degree_type"):
            deg_map[code] = str(row["degree_type"])
    return major_map, cat_map, deg_map

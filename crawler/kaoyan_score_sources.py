"""
掌上考研（zhijiao.cn / kaoyan.cn）复试分数线解析。
"""
from __future__ import annotations

import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("kaoyan_scores")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

ZHIJIAO_BASE = "https://www.zhijiao.cn/kaoyan/web/school"
KAOYAN_H5_SCORE_URL = "https://api.kaoyan.cn/h5/school/schoolScore"
KAOYAN_FACTOR_URL = "https://static.kaoyan.cn/json/factor/{school_id}/factor.json"
DEFAULT_SCORE_KINDS = [f"{i:02d}" for i in range(15)]
CACHE_DIR = Path(__file__).parent / "data"
SCHOOL_ID_CACHE = CACHE_DIR / "kaoyan_school_id_map.json"

_SCORE_HEADERS = (
    "学科门类", "学科名称", "专业名称", "专业",
    "政治分数", "政治单科线", "政治",
    "英语分数", "英语单科线", "英语",
    "业务课一", "业务课二",
    "总分",
)
_CODE_IN_TEXT = re.compile(r"\[(\d{6})\]\s*(.+)")
_DIGIT = re.compile(r"^\d{1,3}$")


def _headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.kaoyan.cn/",
    }


def _fast_mode() -> bool:
    import os
    return os.environ.get("CRAWLER_FAST", "").strip() in ("1", "true", "yes")


def delay_bounds(default_min: float = 2.0, default_max: float = 5.0) -> tuple[float, float]:
    if _fast_mode():
        return 0.35, 0.85
    return default_min, default_max


def polite_sleep(min_s: float = 2.0, max_s: float = 5.0) -> None:
    if _fast_mode():
        min_s, max_s = delay_bounds()
    time.sleep(random.uniform(min_s, max_s))


def norm_name(name: str) -> str:
    s = re.sub(r"\s+", "", (name or "").strip())
    s = re.sub(r"[（(【\[].*?[）)】\]]", "", s)
    return s.lower()


def fetch_html(
    session: requests.Session,
    url: str,
    *,
    min_delay: float = 2.0,
    max_delay: float = 5.0,
    retries: int = 3,
) -> str:
    if _fast_mode():
        min_delay, max_delay = delay_bounds()
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        polite_sleep(min_delay, max_delay)
        try:
            resp = session.get(url, headers=_headers(), timeout=35)
            if resp.status_code == 200 and len(resp.text) > 500:
                resp.encoding = resp.apparent_encoding or "utf-8"
                return resp.text
            log.debug("HTTP %s len=%s url=%s", resp.status_code, len(resp.text), url[-70:])
        except Exception as exc:
            last_exc = exc
            log.debug("fetch fail %s: %s", url[-60:], exc)
        time.sleep(1.5 * (attempt + 1))
    if last_exc:
        log.warning("放弃请求 %s: %s", url[-70:], last_exc)
    return ""


def schoolscorelist_url(
    school_id: int,
    year: int,
    *,
    degree_type: int = 1,
    area_type: str = "A",
    page: int = 1,
) -> str:
    q = urlencode({
        "school_id": school_id,
        "fyear": year,
        "degree_type": degree_type,
        "area_type": area_type,
        "page": page,
    })
    return f"{ZHIJIAO_BASE}/schoolscorelist?{q}"


def schoolscore_url(school_id: int, area_type: str = "A") -> str:
    return f"{ZHIJIAO_BASE}/schoolscore?school_id={school_id}&area_type={area_type}"


def schooldepart_url(depart_id: int) -> str:
    return f"{ZHIJIAO_BASE}/schooldepart?depart_id={depart_id}"


def parse_title_school_name(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html)
    if not m:
        return ""
    title = m.group(1)
    title = re.sub(r"考研复试分数线.*", "", title)
    title = re.sub(r"研究生院.*", "", title)
    title = re.sub(r"-掌上考研.*", "", title)
    return title.strip()


def _parse_int(cell: str) -> Optional[int]:
    cell = (cell or "").strip()
    if not cell or cell in ("-", "—", "/", "无"):
        return None
    if not _DIGIT.match(cell):
        return None
    v = int(cell)
    return v if 0 <= v <= 500 else None


def _header_map(headers: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for i, h in enumerate(headers):
        h = h.strip()
        if "学科" in h or "专业" in h:
            mapping.setdefault("subject", i)
        elif "政治" in h:
            mapping["politics"] = i
        elif "英语" in h:
            mapping["english"] = i
        elif "业务课一" in h or ("业务" in h and "一" in h):
            mapping["pro1"] = i
        elif "业务课二" in h or ("业务" in h and "二" in h):
            mapping["pro2"] = i
        elif "单科" in h and "100" in h and "politics" not in mapping:
            mapping.setdefault("single100", i)
        elif "单科" in h and "100" not in h:
            mapping.setdefault("single150", i)
        elif "总分" in h:
            mapping["total"] = i
    # 旧版：学科门类 | 总分 | 单科(满分=100) | 单科(满分>100)
    if "subject" not in mapping and len(headers) >= 4:
        mapping["subject"] = 0
        if "total" not in mapping and len(headers) >= 2:
            mapping["total"] = 1
    return mapping


def parse_score_table(html: str, year: int, degree_label: str) -> list[dict]:
    """解析 schoolscorelist 表格行。"""
    soup = BeautifulSoup(html, "lxml")
    rows_out: list[dict] = []

    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if len(trs) < 2:
            continue
        header_cells = [c.get_text(" ", strip=True) for c in trs[0].find_all(["th", "td"])]
        if not header_cells:
            continue
        if not any(k in "".join(header_cells) for k in ("总分", "政治", "学科", "专业")):
            continue
        cmap = _header_map(header_cells)

        for tr in trs[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            subject = cells[cmap["subject"]] if "subject" in cmap and cmap["subject"] < len(cells) else ""
            if not subject or subject in _SCORE_HEADERS:
                continue
            if any(k in subject for k in ("广告", "咨询", "版权", "客服")):
                continue

            politics = english = pro1 = pro2 = total = None
            if "politics" in cmap:
                politics = _parse_int(cells[cmap["politics"]])
            if "english" in cmap:
                english = _parse_int(cells[cmap["english"]])
            if "pro1" in cmap:
                pro1 = _parse_int(cells[cmap["pro1"]])
            if "pro2" in cmap:
                pro2 = _parse_int(cells[cmap["pro2"]])
            if "total" in cmap:
                total = _parse_int(cells[cmap["total"]])

            # 兼容「总分 | 单科100 | 单科>100」三列版
            if total is None and len(cells) >= 4:
                total = _parse_int(cells[1])
                politics = politics or _parse_int(cells[2])
                english = english or _parse_int(cells[2])
                pro1 = pro1 or _parse_int(cells[3])

            if total is None and politics is None:
                continue

            rows_out.append({
                "year": year,
                "degree_type": degree_label,
                "major_name": subject.strip(),
                "politics_score": politics,
                "english_score": english,
                "professional1_score": pro1,
                "professional2_score": pro2,
                "total_score": total,
                "source": "kaoyan",
            })
    return rows_out


def discover_pagination_pages(html: str) -> list[int]:
    pages = {1}
    for m in re.finditer(r"[?&]page=(\d+)", html):
        pages.add(int(m.group(1)))
    return sorted(pages)


def parse_departments(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    seen: set[int] = set()
    for a in soup.find_all("a", href=True):
        m = re.search(r"depart_id=(\d+)", a["href"])
        if not m:
            continue
        did = int(m.group(1))
        if did in seen:
            continue
        college = a.get_text(strip=True)
        if not college or len(college) < 2:
            continue
        if any(k in college for k in ("广告", "更多", "首页", "返回")):
            continue
        seen.add(did)
        out.append({"depart_id": did, "college": college[:80]})
    return out


def parse_department_majors(html: str, college: str) -> list[dict]:
    """从 schooldepart 页提取 [代码] 专业名。"""
    soup = BeautifulSoup(html, "lxml")
    majors: list[dict] = []
    seen: set[str] = set()

    text = soup.get_text("\n", strip=True)
    for line in text.splitlines():
        m = _CODE_IN_TEXT.search(line)
        if not m:
            continue
        code, name = m.group(1), m.group(2).strip()
        if code in seen:
            continue
        seen.add(code)
        majors.append({
            "major_code": code,
            "major_name": name[:80],
            "college": college,
        })

    if majors:
        return majors

    # 兜底：页面标题
    title = (soup.title.string or "") if soup.title else ""
    tm = re.search(r"\[(\d{6})\]([^\[]+)", title)
    if tm:
        majors.append({
            "major_code": tm.group(1),
            "major_name": tm.group(2).strip()[:80],
            "college": college,
        })
    return majors


def load_school_id_cache() -> dict[str, int]:
    if SCHOOL_ID_CACHE.exists():
        try:
            raw = json.loads(SCHOOL_ID_CACHE.read_text(encoding="utf-8"))
            return {str(k): int(v) for k, v in raw.items()}
        except Exception:
            pass
    return {}


def save_school_id_cache(mapping: dict[str, int]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SCHOOL_ID_CACHE.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def resolve_school_id(
    session: requests.Session,
    school_name: str,
    cache: dict[str, int],
    *,
    scan_max: int = 1200,
) -> Optional[int]:
    if school_name in cache:
        return cache[school_name]

    short = norm_name(school_name)
    for name, sid in cache.items():
        if norm_name(name) == short or short in norm_name(name) or norm_name(name) in short:
            return sid

    # 增量扫描 zhijiao school_id
    for sid in range(1, scan_max + 1):
        if sid in cache.values():
            continue
        url = schoolscore_url(sid)
        html = fetch_html(session, url, min_delay=1.0, max_delay=2.0)
        if not html or len(html) < 3000:
            continue
        title_name = parse_title_school_name(html)
        if not title_name:
            continue
        cache[title_name] = sid
        if norm_name(title_name) == short or school_name in title_name or title_name in school_name:
            save_school_id_cache(cache)
            return sid

    save_school_id_cache(cache)
    return cache.get(school_name)


def _h5_headers() -> dict[str, str]:
    return {
        **_headers(),
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referer": "https://m.kaoyan.cn/",
        "Origin": "https://m.kaoyan.cn",
    }


def fetch_factor_meta(session: requests.Session, school_id: int) -> dict:
    url = KAOYAN_FACTOR_URL.format(school_id=school_id)
    try:
        resp = session.get(url, headers=_headers(), timeout=25)
        if resp.status_code == 200:
            payload = resp.json()
            if isinstance(payload, dict):
                return payload.get("data") or {}
    except Exception as exc:
        log.debug("factor meta %s: %s", school_id, exc)
    return {}


def _kinds_for_year(factor: dict, year: int, degree_type: int) -> list[str]:
    kind_map = factor.get("kind") or {}
    year_kinds = kind_map.get(str(year)) or kind_map.get(year) or {}
    kinds = year_kinds.get(str(degree_type)) or year_kinds.get(degree_type)
    if kinds:
        return [str(k) for k in kinds]
    return DEFAULT_SCORE_KINDS


def _h5_item_to_row(item: dict, year: int, degree_label: str) -> Optional[dict]:
    total = item.get("total")
    if total is None:
        return None
    dt = item.get("degree_type")
    if dt == 1:
        degree_label = "专硕"
    elif dt == 2:
        degree_label = "学硕"
    college = (item.get("depart_name") or "").strip()
    if item.get("data_type") == "score_level" or college in ("全校或院系", ""):
        college = college if college and college != "全校或院系" else ""
    pro2 = item.get("special_two")
    return {
        "year": year,
        "degree_type": degree_label,
        "major_name": (item.get("name") or "").strip(),
        "major_code": (item.get("code") or "").strip(),
        "college": college,
        "politics_score": item.get("politics"),
        "english_score": item.get("english"),
        "professional1_score": item.get("special_one"),
        "professional2_score": pro2 if pro2 else None,
        "total_score": total,
        "line_diff": item.get("diff_total"),
        "source": "kaoyan_h5",
        "data_type": item.get("data_type"),
    }


def fetch_school_score_h5(
    session: requests.Session,
    school_id: int,
    year: int,
    *,
    area: str = "A",
    factor: Optional[dict] = None,
) -> list[dict]:
    """掌上考研新版 API（api.kaoyan.cn），2023+ 复试线。"""
    factor = factor if factor is not None else fetch_factor_meta(session, school_id)
    seen: set[tuple] = set()
    rows: list[dict] = []

    for degree_type, degree_label in ((2, "学硕"), (1, "专硕")):
        kinds = _kinds_for_year(factor, year, degree_type)
        for kind in kinds:
            payload = {
                "school_id": school_id,
                "year": year,
                "type": degree_type,
                "kind": kind,
                "page": 1,
                "area": area,
            }
            try:
                resp = session.post(
                    KAOYAN_H5_SCORE_URL,
                    json=payload,
                    headers=_h5_headers(),
                    timeout=35,
                )
                if resp.status_code != 200:
                    continue
                body = resp.json()
                if body.get("code") != "0000":
                    continue
                items = body.get("data") or []
            except Exception as exc:
                log.debug("h5 score %s %s kind=%s: %s", school_id, year, kind, exc)
                continue

            for item in items:
                if item.get("data_type") not in ("school_score", "score_level"):
                    continue
                key = (
                    item.get("data_type"),
                    item.get("id"),
                    item.get("code"),
                    item.get("name"),
                    item.get("depart_id"),
                    item.get("degree_type"),
                )
                if key in seen:
                    continue
                seen.add(key)
                row = _h5_item_to_row(item, year, degree_label)
                if row:
                    rows.append(row)

    # 院线优先：同专业名保留 school_score
    by_name: dict[tuple[str, str, int], dict] = {}
    for row in rows:
        k = (row["major_name"], row["degree_type"], row["year"])
        existing = by_name.get(k)
        if not existing or (
            row.get("data_type") == "school_score"
            and existing.get("data_type") != "school_score"
        ):
            by_name[k] = row
    return list(by_name.values())


def fetch_school_score_pages(
    session: requests.Session,
    school_id: int,
    year: int,
    *,
    degree_type: int,
    degree_label: str,
) -> list[dict]:
    all_rows: list[dict] = []
    seen_pages: set[int] = set()
    queue = [1]

    while queue:
        page = queue.pop(0)
        if page in seen_pages:
            continue
        seen_pages.add(page)

        url = schoolscorelist_url(school_id, year, degree_type=degree_type, page=page)
        html = fetch_html(session, url)
        if not html:
            continue

        rows = parse_score_table(html, year, degree_label)
        if rows:
            all_rows.extend(rows)

        for p in discover_pagination_pages(html):
            if p not in seen_pages:
                queue.append(p)

    return all_rows


def fetch_school_major_index(
    session: requests.Session,
    school_id: int,
    *,
    depart_workers: int = 0,
) -> list[dict]:
    html = fetch_html(session, schoolscore_url(school_id))
    if not html:
        return []
    departments = parse_departments(html)
    if not departments:
        return []

    workers = depart_workers or (12 if _fast_mode() else 1)
    if workers <= 1:
        majors: list[dict] = []
        for dep in departments:
            dhtml = fetch_html(session, schooldepart_url(dep["depart_id"]))
            if not dhtml:
                continue
            majors.extend(parse_department_majors(dhtml, dep["college"]))
        return majors

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_dep(dep: dict) -> list[dict]:
        local = requests.Session()
        dhtml = fetch_html(local, schooldepart_url(dep["depart_id"]))
        if not dhtml:
            return []
        return parse_department_majors(dhtml, dep["college"])

    majors = []
    with ThreadPoolExecutor(max_workers=min(workers, len(departments))) as pool:
        futures = [pool.submit(_fetch_dep, dep) for dep in departments]
        for fut in as_completed(futures):
            try:
                majors.extend(fut.result())
            except Exception as exc:
                log.debug("depart fetch: %s", exc)
    return majors


def match_major_meta(score_name: str, majors: list[dict]) -> Optional[dict]:
    target = norm_name(score_name)
    if not target:
        return None

    best: Optional[dict] = None
    best_len = 0
    for m in majors:
        mn = norm_name(m.get("major_name", ""))
        if not mn:
            continue
        if mn == target:
            return m
        if target in mn or mn in target:
            overlap = min(len(target), len(mn))
            if overlap > best_len:
                best_len = overlap
                best = m
    return best

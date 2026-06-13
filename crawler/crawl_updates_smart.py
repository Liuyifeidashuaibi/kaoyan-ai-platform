#!/usr/bin/env python3
"""
crawl_updates_smart.py — 智能增量动态数据更新
============================================================
每年更新数据（每日 / 每周自动运行）：
  招生简章 · 招生目录 · 复试分数线 · 拟录取名单
  推免公告 · 调剂信息 · 报录比

核心能力：
  ✓ 季节性智能调度（招生季/复试季/淡季自动切换）
  ✓ MD5 哈希去重：内容未变化则跳过，零 token 浪费
  ✓ 多数据源：学校官网 + 全国研招网(chsi) + Jina Reader
  ✓ 通义千问 AI 解析，无需 CSS 选择器，通吃所有院校
  ✓ 异步并发 + UA 池 + 指数退避重试
  ✓ --force 强制全量更新，--season 手动指定季节

依赖：pip install aiohttp openai supabase python-dotenv
"""

import argparse
import asyncio
import hashlib
import logging
import os
import random
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import aiohttp
from aiohttp import TCPConnector, ClientSession
from dotenv import load_dotenv
from supabase import create_client, Client

from crawl_basic_once import majors_to_rows
from enrich_constants import (
    TARGET_YEAR,
    extract_dates_from_text,
    infer_rec_status,
    infer_rec_type,
)
from llm_parser import ParseCache, clean_page_content, qwen_extract

# ── 环境变量 ──────────────────────────────────────────────────────────────────
_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
DASHSCOPE_KEY = os.environ.get("DASHSCOPE_API_KEY", "")

# ── 日志 ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_here / "updates.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("update")

# ── UA 池 ─────────────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.52 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
]

# ── 季节判断与数据类型映射 ────────────────────────────────────────────────────
SEASON_MAP = {
    "招生季": ["招生简章", "招生目录", "推免公告"],   # 9-11 月
    "复试季": ["复试分数线", "拟录取名单", "调剂信息", "报录比"],  # 3-5 月
    "淡季":   ["招生简章", "招生目录", "复试分数线", "拟录取名单",
               "推免公告", "调剂信息", "报录比"],  # 其他月份
}

ALL_TYPES = set(t for types in SEASON_MAP.values() for t in types)


def detect_season() -> str:
    m = date.today().month
    if 9 <= m <= 11:
        return "招生季"
    if 3 <= m <= 5:
        return "复试季"
    return "淡季"


# ── 工具函数 ──────────────────────────────────────────────────────────────────
def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def safe_date(raw: Any) -> str:
    """将各种日期格式归一为 YYYY-MM-DD，失败返回今天"""
    if not raw:
        return date.today().isoformat()
    s = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%Y.%m.%d"):
        try:
            return datetime.strptime(s[:10], fmt[:len(s[:10])]).date().isoformat()
        except ValueError:
            pass
    return s[:10] if len(s) >= 10 else date.today().isoformat()


# ── Jina Reader ────────────────────────────────────────────────────────────────
JINA_BASE = "https://r.jina.ai/"
MAX_CHARS = 12_000


async def jina_fetch(session: ClientSession, url: str) -> Optional[str]:
    """Jina Reader：任意 URL → 干净 Markdown，无需处理 JS/编码/防爬"""
    try:
        async with session.get(
            f"{JINA_BASE}{url}",
            headers={
                "Accept": "text/plain",
                "X-Timeout": "25",
                "User-Agent": random.choice(USER_AGENTS),
            },
            timeout=aiohttp.ClientTimeout(total=50),
        ) as resp:
            if resp.status == 200:
                return (await resp.text())[:MAX_CHARS]
            log.debug("Jina %s → %s", url[-60:], resp.status)
    except Exception as exc:
        log.debug("Jina error %s: %s", url[-60:], exc)
    return None


# ── HTTP 直接抓取（带重试，用于研招网等简单页面）─────────────────────────────
_RETRY_STATUS = {429, 500, 502, 503, 504}


async def http_get(session: ClientSession, url: str, retries: int = 3) -> Optional[str]:
    for attempt in range(retries):
        try:
            await asyncio.sleep(random.uniform(1.0, 2.5))
            async with session.get(
                url,
                headers={"User-Agent": random.choice(USER_AGENTS),
                         "Accept": "text/html,*/*",
                         "Accept-Language": "zh-CN,zh;q=0.9"},
                timeout=aiohttp.ClientTimeout(total=30),
                allow_redirects=True,
            ) as resp:
                if resp.status in _RETRY_STATUS:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if resp.status == 200:
                    return await resp.text(errors="replace")
        except asyncio.TimeoutError:
            log.warning("[HTTP] timeout %s (attempt %d)", url[-60:], attempt + 1)
            await asyncio.sleep(2 ** attempt)
        except aiohttp.ClientError as exc:
            log.warning("[HTTP] %s: %s (attempt %d)", url[-60:], exc, attempt + 1)
            await asyncio.sleep(2 ** attempt)
    log.error("[HTTP] FAILED %s", url[-80:])
    return None


# ── Supabase 读写层 ────────────────────────────────────────────────────────────
class DB:
    def __init__(self) -> None:
        self._sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # ── 读 ──────────────────────────────────────────────────────────────────
    def get_universities(self) -> list[dict]:
        try:
            res = self._sb.table("universities").select(
                "id,name,website,graduate_url,school_code"
            ).execute()
            return res.data or []
        except Exception as exc:
            log.error("get_universities: %s", exc)
            return []

    def get_content_hash(self, table: str, university_id: str, url: str) -> Optional[str]:
        """查询已有记录的 content_hash（增量去重核心）"""
        try:
            res = (self._sb.table(table).select("content_hash")
                   .eq("university_id", university_id)
                   .eq("url", url)
                   .maybe_single().execute())
            return (res.data or {}).get("content_hash")
        except Exception:
            return None

    def get_last_updated(self, table: str, university_id: str) -> Optional[datetime]:
        try:
            res = (self._sb.table(table).select("last_updated")
                   .eq("university_id", university_id)
                   .order("last_updated", desc=True)
                   .limit(1).execute())
            if res.data and res.data[0].get("last_updated"):
                return datetime.fromisoformat(
                    res.data[0]["last_updated"].replace("Z", "+00:00")
                )
        except Exception:
            pass
        return None

    # ── 写 ──────────────────────────────────────────────────────────────────
    def upsert_announcement(self, row: dict) -> bool:
        try:
            self._sb.table("announcements").upsert(
                row, on_conflict="university_id,url"
            ).execute()
            return True
        except Exception as exc:
            log.error("upsert_announcement: %s", exc)
            return False

    def upsert_recommendation(self, row: dict) -> bool:
        try:
            self._sb.table("recommendations").upsert(
                row, on_conflict="university_id,url"
            ).execute()
            return True
        except Exception as exc:
            log.error("upsert_recommendation: %s", exc)
            return False

    def upsert_adjustment(self, row: dict) -> bool:
        try:
            self._sb.table("adjustments").upsert(
                row, on_conflict="university_id,major_name,year"
            ).execute()
            return True
        except Exception as exc:
            log.error("upsert_adjustment: %s", exc)
            return False

    def upsert_score(self, row: dict) -> bool:
        try:
            self._sb.table("scores").upsert(
                row, on_conflict="major_id,year"
            ).execute()
            return True
        except Exception as exc:
            log.error("upsert_score: %s", exc)
            return False

    def upsert_majors(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        deduped: dict[tuple[str, str, str, str], dict] = {}
        for r in rows:
            key = (
                r["university_id"],
                r["code"],
                r["degree_type"],
                r["study_mode"],
            )
            prev = deduped.get(key)
            if not prev or len(r.get("college", "")) > len(prev.get("college", "")):
                deduped[key] = r
        try:
            res = self._sb.table("majors").upsert(
                list(deduped.values()),
                on_conflict="university_id,code,degree_type,study_mode",
            ).execute()
            return len(res.data or [])
        except Exception as exc:
            log.error("upsert_majors: %s", exc)
            return 0

    def get_major_map(self, university_id: str) -> dict[str, str]:
        """6 位专业代码 → major_id"""
        try:
            res = (
                self._sb.table("majors")
                .select("id,code")
                .eq("university_id", university_id)
                .execute()
            )
            out: dict[str, str] = {}
            for row in res.data or []:
                code = re.sub(r"\D", "", str(row.get("code") or ""))[:6]
                if len(code) == 6:
                    out[code] = row["id"]
            return out
        except Exception as exc:
            log.error("get_major_map: %s", exc)
            return {}

    def get_major_name_map(self, university_id: str) -> dict[str, str]:
        """专业名称 → major_id"""
        try:
            res = (
                self._sb.table("majors")
                .select("id,name")
                .eq("university_id", university_id)
                .execute()
            )
            return {
                str(row.get("name") or "").strip(): row["id"]
                for row in (res.data or [])
                if row.get("name")
            }
        except Exception as exc:
            log.error("get_major_name_map: %s", exc)
            return {}


# ── 数据分发：AI 结果 → 对应表 ───────────────────────────────────────────────
def _make_url_key(item_link: Any, source_url: str, title: str) -> str:
    """优先用 AI 提取的 link，否则用 source_url + title hash 保证唯一性"""
    link = str(item_link or "").strip()
    if link.startswith("http"):
        return link[:500]
    suffix = md5(title)[:8] if title else md5(source_url)[:8]
    return f"{source_url}#{suffix}"[:500]


def _ann_type(dtype: str) -> str:
    if dtype == "招生简章":
        return "招生简章"
    if dtype in ("调剂信息",):
        return "调剂公告"
    if dtype == "推免公告":
        return "推免公告"
    return "招生公告"


def _parse_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    m = re.search(r"\d+", str(val))
    return int(m.group()) if m else None


_COLLEGE_RE = re.compile(r"学院|系|中心|部|研究所|研究院|实验室")


def _college_from_item(item: dict) -> str:
    college = str(item.get("college") or "").strip()
    if college and college != "未知学院" and _COLLEGE_RE.search(college):
        return college[:100]
    return ""


def _with_college_content(college: str, content: str) -> str:
    if not college:
        return content
    prefix = f"【{college}】"
    if content.startswith(prefix):
        return content[:1000]
    body = content.strip() if content else ""
    return f"{prefix}{body}"[:1000] if body else prefix


def _major_code_from_item(item: dict) -> str:
    for key in ("major_code", "code", "专业代码"):
        raw = item.get(key)
        if raw:
            digits = re.sub(r"\D", "", str(raw))[:6]
            if len(digits) == 6:
                return digits
    majors = item.get("major")
    candidates: list[str] = []
    if isinstance(majors, list):
        candidates.extend(str(x) for x in majors)
    elif isinstance(majors, str):
        candidates.append(majors)
    candidates.append(str(item.get("major_name") or item.get("title") or ""))
    for text in candidates:
        m = re.search(r"(0\d{5})", text)
        if m:
            return m.group(1)
    return ""


def _major_name_from_item(item: dict) -> str:
    majors = item.get("major")
    if isinstance(majors, list) and majors:
        name = str(majors[0]).strip()
    elif isinstance(majors, str):
        name = majors.strip()
    else:
        name = str(item.get("major_name") or item.get("title") or "").strip()
    name = re.sub(r"\(0\d{5}\)|（0\d{5}）", "", name).strip()
    name = re.sub(r"0\d{5}", "", name).strip()
    return name[:100]


def upsert_score_from_item(
    db: "DB",
    uid: str,
    item: dict,
    year: int,
    major_map: dict[str, str],
    name_map: dict[str, str],
) -> bool:
    """将单条复试线 AI/正则结果写入 scores 表。"""
    code = _major_code_from_item(item)
    major_name = _major_name_from_item(item)
    major_id = major_map.get(code) if code else None
    if not major_id:
        major_id = _resolve_major_id(item, major_name, major_map, name_map)

    total = _parse_int(
        item.get("total_score") or item.get("score") or item.get("总分") or item.get("复试线")
    )
    if not major_id or not total or total < 140 or total > 510:
        return False

    politics = _parse_int(
        item.get("politics_score") or item.get("政治") or item.get("政综")
    )
    english = _parse_int(
        item.get("english_score") or item.get("外语") or item.get("英语")
    )
    pro1 = _parse_int(
        item.get("professional1_score") or item.get("业务课一") or item.get("专业课一")
    )
    pro2 = _parse_int(
        item.get("professional2_score") or item.get("业务课二") or item.get("专业课二")
    )
    line_diff = _parse_int(item.get("line_diff"))

    return db.upsert_score({
        "university_id": uid,
        "major_id": major_id,
        "year": year,
        "total_score": total,
        "politics_score": politics if politics is not None else 0,
        "english_score": english if english is not None else 0,
        "professional1_score": pro1,
        "professional2_score": pro2,
        "line_diff": line_diff,
    })


_DETAIL_KW = ("调剂", "推免", "复试", "分数线", "招生", "简章", "目录", "夏令营", "录取", "报录比")


def collect_detail_urls(
    extracted: Any,
    cleaned: str,
    source_url: str,
    limit: int = 5,
) -> list[str]:
    """从 AI 结果与 Markdown 链接中收集值得深度抓取的详情页 URL"""
    urls: list[str] = []
    seen: set[str] = {source_url.rstrip("/")}

    items: list[dict] = []
    if isinstance(extracted, list):
        items = [x for x in extracted if isinstance(x, dict)]
    elif isinstance(extracted, dict):
        items = [extracted]

    for item in items:
        link = str(item.get("link") or "").strip().split("?")[0]
        if link.startswith("http") and link not in seen:
            seen.add(link)
            urls.append(link)

    for title, href in re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", cleaned):
        if not any(kw in title for kw in _DETAIL_KW):
            continue
        link = href.strip().split("?")[0]
        if link.startswith("http") and link not in seen:
            seen.add(link)
            urls.append(link)

    return urls[:limit]


def _resolve_major_id(
    item: dict,
    major_name: str,
    major_map: dict[str, str],
    name_map: dict[str, str],
) -> Optional[str]:
    code = _major_code_from_item(item)
    if code and code in major_map:
        return major_map[code]
    if major_name and major_name in name_map:
        return name_map[major_name]
    if major_name:
        for name, mid in name_map.items():
            if name in major_name or major_name in name:
                return mid
    return None


def regex_extract_from_markdown(content: str) -> list[dict]:
    """AI 不可用时的 Markdown 链接兜底"""
    items: list[dict] = []
    seen: set[str] = set()
    patterns = (
        (r"复试|分数线|录取线", "复试分数线"),
        (r"调剂", "调剂信息"),
        (r"推免|夏令营|预推免", "推免公告"),
        (r"招生简章|章程", "招生简章"),
        (r"专业目录|招生目录|招生计划", "招生目录"),
        (r"招生|研招", "招生公告"),
    )
    for title, href in re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", content):
        title = title.strip()
        if len(title) < 4 or title in seen:
            continue
        dtype = None
        for kw, t in patterns:
            if re.search(kw, title):
                dtype = t
                break
        if not dtype:
            continue
        seen.add(title)
        items.append({
            "type": dtype,
            "title": title[:200],
            "link": href.split("?")[0],
            "publish_time": date.today().isoformat(),
            "content": "",
        })
    return items[:40]


def dispatch(
    db: DB,
    uid: str,
    items: Any,
    source_url: str,
    page_hash: str,
    target_types: list[str],
    major_map: Optional[dict[str, str]] = None,
    name_map: Optional[dict[str, str]] = None,
) -> dict[str, int]:
    stats = {
        "announcements": 0,
        "recommendations": 0,
        "adjustments": 0,
        "scores": 0,
        "majors": 0,
        "skipped": 0,
    }
    major_map = major_map or {}
    name_map = name_map or {}

    if not items:
        return stats
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return stats

    now_iso = datetime.utcnow().isoformat()
    cur_year = date.today().year

    for item in items:
        if not isinstance(item, dict):
            continue

        dtype = str(item.get("type") or "").strip()
        if dtype not in target_types:
            stats["skipped"] += 1
            continue

        title = str(item.get("title") or "").strip()
        pub_time = safe_date(item.get("publish_time"))
        content = str(item.get("content") or "").strip()[:1000]
        year = int(item.get("year") or cur_year) if str(item.get("year") or "").isdigit() else cur_year
        url_key = _make_url_key(item.get("link"), source_url, title)
        pub_year = int(pub_time[:4]) if pub_time and pub_time[:4].isdigit() else cur_year
        accept_years = {TARGET_YEAR, TARGET_YEAR + 1}
        is_target_year = (
            year in accept_years
            or pub_year in accept_years
            or str(TARGET_YEAR) in title
            or str(TARGET_YEAR + 1) in title
        )

        # ── 校验关键字段 ──────────────────────────────────────────────────
        if not title:
            stats["skipped"] += 1
            continue

        if not is_target_year:
            stats["skipped"] += 1
            continue

        if dtype in ("复试分数线", "调剂信息"):
            year = TARGET_YEAR

        college = _college_from_item(item)
        ann_content = _with_college_content(college, content)

        ann_row = {
            "university_id": uid,
            "title": title[:200],
            "publish_time": pub_time,
            "url": url_key,
            "type": _ann_type(dtype),
            "content": ann_content or None,
            "content_hash": page_hash,
            "last_updated": now_iso,
        }

        # ── 分发路由 ─────────────────────────────────────────────────────
        if dtype in ("招生简章", "招生公告", "招生目录", "复试分数线", "拟录取名单", "报录比"):
            if db.upsert_announcement(ann_row):
                stats["announcements"] += 1

        if dtype == "复试分数线":
            if upsert_score_from_item(db, uid, item, year, major_map, name_map):
                stats["scores"] += 1

        if dtype == "推免公告":
            if db.upsert_announcement(ann_row):
                stats["announcements"] += 1
            start_raw = item.get("start_time")
            end_raw = item.get("end_time")
            start_t = safe_date(start_raw) if start_raw else None
            end_t = safe_date(end_raw) if end_raw else None
            if not start_t and not end_t:
                ds, de = extract_dates_from_text(f"{title} {content}")
                start_t, end_t = ds, de
            rec_type = infer_rec_type(title)
            rec_status = infer_rec_status(start_t, end_t)
            row = {
                "university_id": uid,
                "title": title[:200],
                "type": rec_type,
                "status": rec_status,
                "start_time": start_t,
                "end_time": end_t,
                "url": url_key,
                "content": ann_content or None,
                "content_hash": page_hash,
                "last_updated": now_iso,
            }
            if db.upsert_recommendation(row):
                stats["recommendations"] += 1

        elif dtype == "调剂信息":
            db.upsert_announcement(ann_row)
            stats["announcements"] += 1
            major_list = item.get("major") or []
            major_name = (
                major_list[0] if isinstance(major_list, list) and major_list
                else str(major_list or "不限")
            )[:100]
            req_parts = []
            if college:
                req_parts.append(f"学院：{college}")
            if content:
                req_parts.append(content)
            major_id = _resolve_major_id(item, major_name, major_map, name_map)
            row = {
                "university_id": uid,
                "major_id": major_id,
                "major_name": major_name,
                "year": year,
                "quota": _parse_int(item.get("quota")),
                "requirements": " · ".join(req_parts) or None,
                "contact": str(item.get("contact") or "")[:200] or None,
                "url": url_key[:300],
                "content_hash": page_hash,
                "last_updated": now_iso,
            }
            if db.upsert_adjustment(row):
                stats["adjustments"] += 1

        if dtype == "招生目录":
            code = _major_code_from_item(item)
            major_list = item.get("major") or []
            if isinstance(major_list, str):
                major_list = [major_list]
            mname = (
                str(major_list[0]).strip()[:100]
                if isinstance(major_list, list) and major_list
                else ""
            )
            if code and mname:
                rows = majors_to_rows(
                    [{"code": code, "name": mname, "college": college or ""}],
                    uid,
                )
                if rows and db.upsert_majors(rows):
                    stats["majors"] += len(rows)

    return stats


# ── 数据源 URL 生成 ────────────────────────────────────────────────────────────
_GRAD_PATHS = [
    "/yjszs/tzgg/",    # 研招所/通知公告（最常见）
    "/yjszs/",
    "/yjsy/news/",
    "/yjsy/",
    "/graduate/news/",
    "/graduate/",
]


_SCORE_PATHS = [
    "/yjszs/zsxx/fsx.htm",
    "/yjszs/fsx/",
    "/yjszs/zsxx/cjcx.htm",
    "/yjsy/zsxx/fsx.htm",
    "/graduate/admission/fsx",
    "/yz/fsx",
    "/info/1145/",
    "/zxgg.htm",
    "/yjszs/zsxx/zxgg.htm",
]


def build_score_urls(
    website: str,
    grad_url: Optional[str],
    name: str,
    school_code: Optional[str] = None,
) -> list[str]:
    """复试分数线候选 URL（优先研招/研究生院子页）"""
    base = (website or "").rstrip("/")
    urls: list[str] = []
    if school_code:
        sc = re.sub(r"\D", "", str(school_code))[:5]
        if sc:
            urls.append(
                f"https://yz.chsi.com.cn/sch/schoolInfo--schId-{sc}.dhtml"
            )
    if grad_url and grad_url.startswith("http"):
        urls.append(grad_url)
        gbase = grad_url.rstrip("/")
        for path in _SCORE_PATHS:
            u = f"{gbase}{path}" if path.startswith("/") else f"{gbase}/{path}"
            if u not in urls:
                urls.append(u)
    for path in _SCORE_PATHS:
        u = f"{base}{path}"
        if u not in urls:
            urls.append(u)
    for path in _GRAD_PATHS:
        u = f"{base}{path}"
        if u not in urls:
            urls.append(u)
    urls.append(f"https://yz.chsi.com.cn/sch/schInfo.do?searchType=1&keyword={name}")
    return urls


def collect_score_detail_urls(cleaned: str, source_url: str, limit: int = 8) -> list[str]:
    """从页面 Markdown 链接中收集复试线详情页"""
    urls: list[str] = []
    seen: set[str] = {source_url.rstrip("/")}
    score_kw = ("复试", "分数线", "录取线", "院线", "校线", "基本线", "初试成绩")
    for title, href in re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", cleaned):
        if not any(kw in title for kw in score_kw):
            continue
        link = href.strip().split("?")[0]
        if link.startswith("http") and link not in seen:
            seen.add(link)
            urls.append(link)
    return urls[:limit]


def regex_extract_scores(content: str, year: int = TARGET_YEAR) -> list[dict]:
    """从表格/Markdown 文本正则兜底提取复试分数线"""
    items: list[dict] = []
    seen: set[str] = set()

    def _push(code: str, nums: list[int], line: str) -> None:
        if code in seen or not nums:
            return
        total = nums[0]
        if total < 140 or total > 510:
            return
        seen.add(code)
        items.append({
            "type": "复试分数线",
            "year": year,
            "major_code": code,
            "total_score": total,
            "politics_score": nums[1] if len(nums) > 1 else None,
            "english_score": nums[2] if len(nums) > 2 else None,
            "professional1_score": nums[3] if len(nums) > 3 else None,
            "professional2_score": nums[4] if len(nums) > 4 else None,
            "title": line[:120],
        })

    for line in content.splitlines():
        if not re.search(r"0\d{5}", line):
            continue
        if not re.search(r"复试|分数|录取线|总分|政治|英语|外语|业务", line, re.I):
            if "|" not in line and not re.search(r"\d{3}", line):
                continue
        code_m = re.search(r"(0\d{5})", line)
        if not code_m:
            continue
        nums = [
            int(n)
            for n in re.findall(r"(?<![\d.])(\d{2,3})(?![\d.])", line)
            if 30 <= int(n) <= 500
        ]
        if nums:
            _push(code_m.group(1), nums, line)

    for row in re.findall(r"\|([^\n\|]*(?:\|[^\n\|]*)+)\|", content):
        if not re.search(r"0\d{5}", row):
            continue
        code_m = re.search(r"(0\d{5})", row)
        if not code_m:
            continue
        nums = [
            int(n)
            for n in re.findall(r"(?<![\d.])(\d{2,3})(?![\d.])", row)
            if 30 <= int(n) <= 500
        ]
        if nums:
            _push(code_m.group(1), nums, row)

    return items[:200]


def build_source_urls(website: str, grad_url: Optional[str], name: str) -> list[str]:
    """生成多个候选数据源 URL，越靠前优先级越高"""
    from grad_announcement_sources import build_grad_announcement_urls

    urls = build_grad_announcement_urls(website, grad_url)
    chsi = f"https://yz.chsi.com.cn/sch/schInfo.do?searchType=1&keyword={name}"
    if chsi not in urls:
        urls.append(chsi)
    return urls


# ── 单所院校增量更新 ──────────────────────────────────────────────────────────
async def _process_page(
    session: ClientSession,
    db: DB,
    uid: str,
    url: str,
    target_types: list[str],
    force: bool,
    parse_cache: ParseCache,
    major_map: dict[str, str],
    name_map: dict[str, str],
) -> dict[str, int]:
    """抓取单页 → AI 解析 → 写库，返回 write_stats"""
    from score_sources import fetch_page_text

    content = await fetch_page_text(session, url)
    if not content or len(content) < 200:
        return {"fetched": 0, "unchanged": 0, "write": {}}

    cleaned = clean_page_content(content)
    page_hash = md5(cleaned)

    if not force:
        existing = db.get_content_hash("announcements", uid, url)
        if existing == page_hash:
            return {"fetched": 1, "unchanged": 1, "write": {}}

    extracted = await qwen_extract(
        cleaned,
        cache=parse_cache,
        content_hash=page_hash,
    )
    if not extracted:
        extracted = regex_extract_from_markdown(cleaned)
    if not extracted:
        return {"fetched": 1, "unchanged": 0, "write": {}}

    write_stats = dispatch(
        db, uid, extracted, url, page_hash, target_types, major_map, name_map
    )
    return {"fetched": 1, "unchanged": 0, "write": write_stats, "cleaned": cleaned, "extracted": extracted}


async def update_university(
    session: ClientSession,
    db: DB,
    uni: dict,
    target_types: list[str],
    force: bool,
    sem: asyncio.Semaphore,
    parse_cache: ParseCache,
    deep_pages: int = 0,
) -> dict:
    name = uni["name"]
    uid = uni["id"]
    website = uni.get("website") or ""
    grad_url = uni.get("graduate_url")

    stats = {
        "name": name, "fetched": 0, "new": 0, "unchanged": 0,
        "scores": 0, "error": None,
    }
    major_map = db.get_major_map(uid)
    name_map = db.get_major_name_map(uid)

    async with sem:
        source_urls = build_source_urls(website, grad_url, name)
        detail_queue: list[str] = []

        for url in source_urls:
            try:
                result = await _process_page(
                    session, db, uid, url, target_types, force,
                    parse_cache, major_map, name_map,
                )
                stats["fetched"] += result.get("fetched", 0)
                stats["unchanged"] += result.get("unchanged", 0)
                write_stats = result.get("write") or {}
                written = sum(v for k, v in write_stats.items() if k != "skipped")
                stats["new"] += written
                stats["scores"] += write_stats.get("scores", 0)

                if deep_pages > 0 and result.get("extracted"):
                    for durl in collect_detail_urls(
                        result["extracted"],
                        result.get("cleaned") or "",
                        url,
                        limit=deep_pages,
                    ):
                        if durl not in detail_queue and len(detail_queue) < deep_pages:
                            detail_queue.append(durl)

            except Exception as exc:
                stats["error"] = str(exc)
                log.exception("[%s] 处理 %s 异常: %s", name, url[-60:], exc)

        # 深度抓取详情页（分数线/调剂/推免正文）
        seen_detail: set[str] = set()
        for durl in detail_queue:
            if durl in seen_detail:
                continue
            seen_detail.add(durl)
            try:
                result = await _process_page(
                    session, db, uid, durl, target_types, force,
                    parse_cache, major_map, name_map,
                )
                stats["fetched"] += result.get("fetched", 0)
                stats["unchanged"] += result.get("unchanged", 0)
                write_stats = result.get("write") or {}
                written = sum(v for k, v in write_stats.items() if k != "skipped")
                stats["new"] += written
                stats["scores"] += write_stats.get("scores", 0)
                await asyncio.sleep(random.uniform(1.0, 2.0))
            except Exception as exc:
                log.debug("[%s] 详情页 %s: %s", name, durl[-50:], exc)

    return stats


# ── 运行摘要 ──────────────────────────────────────────────────────────────────
def print_summary(results: list, season: str, elapsed: float) -> None:
    total = len(results)
    ok = sum(1 for r in results if isinstance(r, dict) and not r.get("error"))
    fetched = sum(r.get("fetched", 0) for r in results if isinstance(r, dict))
    new_items = sum(r.get("new", 0) for r in results if isinstance(r, dict))
    score_items = sum(r.get("scores", 0) for r in results if isinstance(r, dict))
    unchanged = sum(r.get("unchanged", 0) for r in results if isinstance(r, dict))
    errors = [r for r in results if isinstance(r, dict) and r.get("error")]

    log.info("=" * 65)
    log.info("季节: %-6s | 院校: %d/%d | 耗时: %.1fs", season, ok, total, elapsed)
    log.info("页面抓取: %d  |  新增/更新: %d  |  分数线: %d  |  跳过(未变): %d",
             fetched, new_items, score_items, unchanged)
    if errors:
        log.warning("异常院校 (%d): %s", len(errors), ", ".join(r["name"] for r in errors))
    log.info("=" * 65)


# ── 主入口 ────────────────────────────────────────────────────────────────────
async def main(
    force: bool,
    season_override: Optional[str],
    concurrency: int,
    only_school: Optional[str],
    deep_pages: int = 0,
) -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    if not DASHSCOPE_KEY:
        log.error("缺少 DASHSCOPE_API_KEY")
        sys.exit(1)

    season = season_override or detect_season()
    target_types = list(ALL_TYPES) if force else SEASON_MAP[season]

    log.info(
        "季节: %s | 更新类型: %s | force=%s | deep=%d | model=%s",
        season, "、".join(target_types), force, deep_pages,
        os.environ.get("CRAWLER_PARSE_MODEL", "qwen-turbo"),
    )

    db = DB()
    parse_cache = ParseCache()
    universities = db.get_universities()
    if only_school:
        universities = [u for u in universities if only_school in u.get("name", "")]
    if not universities:
        log.error("数据库无院校数据，请先运行 crawl_basic_once.py")
        sys.exit(1)
    log.info("加载 %d 所院校", len(universities))

    sem = asyncio.Semaphore(concurrency)
    connector = TCPConnector(
        limit=concurrency * 5,
        limit_per_host=3,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
    )

    start = time.time()
    async with ClientSession(connector=connector) as session:
        results = await asyncio.gather(
            *[
                update_university(
                    session, db, uni, target_types, force, sem, parse_cache,
                    deep_pages=deep_pages,
                )
                for uni in universities
            ],
            return_exceptions=True,
        )

    print_summary(
        [r for r in results if not isinstance(r, Exception)],
        season,
        time.time() - start,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="智能增量动态数据爬虫（Jina + 通义千问）")
    parser.add_argument(
        "--force", action="store_true",
        help="强制全量更新，忽略 content_hash 增量判断",
    )
    parser.add_argument(
        "--season", choices=list(SEASON_MAP.keys()), default=None,
        help="手动指定季节（默认根据当前日期自动判断）",
    )
    parser.add_argument(
        "--concurrency", type=int, default=3,
        help="同时处理院校数（默认 3）",
    )
    parser.add_argument("--school", default=None, help="只处理指定院校（模糊匹配）")
    parser.add_argument(
        "--deep-pages", type=int, default=0,
        help="每校额外深度抓取 N 条详情页（分数线/调剂/推免正文，默认 0）",
    )
    args = parser.parse_args()
    asyncio.run(main(
        force=args.force,
        season_override=args.season,
        concurrency=args.concurrency,
        only_school=args.school,
        deep_pages=args.deep_pages,
    ))

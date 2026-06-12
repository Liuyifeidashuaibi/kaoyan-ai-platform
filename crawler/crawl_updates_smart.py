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
import json
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
from openai import AsyncOpenAI
from supabase import create_client, Client

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


def parse_json_safe(text: Optional[str]) -> Optional[Any]:
    if not text:
        return None
    text = text.strip()
    for cand in [
        text,
        (m := re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)) and m.group(1),
        (m := re.search(r"\[[\s\S]*\]", text)) and m.group(),
        (m := re.search(r"\{[\s\S]*\}", text)) and m.group(),
    ]:
        if not cand:
            continue
        try:
            return json.loads(cand)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


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


# ── 通义千问 AI 解析 ──────────────────────────────────────────────────────────
_qwen: Optional[AsyncOpenAI] = None


def get_qwen() -> AsyncOpenAI:
    global _qwen
    if _qwen is None:
        _qwen = AsyncOpenAI(
            api_key=DASHSCOPE_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    return _qwen


# 用户指定的通用解析 Prompt（一个 Prompt 通吃所有院校、所有页面结构）
EXTRACT_PROMPT = """\
你是一个专业的考研数据提取专家，请从下面的网页内容中，提取所有考研相关信息，并严格输出JSON格式，不要输出任何其他文字。
需要提取的字段：
- type: 数据类型（只能是：招生简章、招生目录、复试分数线、拟录取名单、推免公告、调剂信息、报录比）
- school: 学校名称
- college: 学院名称
- year: 年份（数字）
- title: 公告标题
- publish_time: 发布时间（YYYY-MM-DD格式）
- content: 核心内容摘要（100-200字）
- major: 涉及专业（数组）
- score: 分数线（如有，数字，没有则为null）
- link: 原文链接

如果某个字段没有信息，填null。
如果页面包含多条信息，输出 JSON 数组；只有一条信息也可以输出单个 JSON 对象。
网页内容：
{clean_html}"""


async def qwen_extract(content: str, retries: int = 3) -> Optional[Any]:
    prompt = EXTRACT_PROMPT.format(clean_html=content)
    for attempt in range(retries):
        try:
            resp = await get_qwen().chat.completions.create(
                model="qwen-max",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,
                temperature=0.05,
            )
            raw = resp.choices[0].message.content
            result = parse_json_safe(raw)
            if result is not None:
                return result
            log.warning("Qwen 返回无法解析为 JSON（attempt %d）", attempt + 1)
        except Exception as exc:
            wait = 2 ** attempt
            if attempt < retries - 1:
                log.warning("Qwen retry %d/%d after %ds: %s", attempt + 1, retries, wait, exc)
                await asyncio.sleep(wait)
            else:
                log.error("Qwen failed after %d retries: %s", retries, exc)
    return None


# ── Supabase 读写层 ────────────────────────────────────────────────────────────
class DB:
    def __init__(self) -> None:
        self._sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # ── 读 ──────────────────────────────────────────────────────────────────
    def get_universities(self) -> list[dict]:
        try:
            res = self._sb.table("universities").select("id,name,website,graduate_url").execute()
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


# ── 数据分发：AI 结果 → 对应表 ───────────────────────────────────────────────
def _make_url_key(item_link: Any, source_url: str, title: str) -> str:
    """优先用 AI 提取的 link，否则用 source_url + title hash 保证唯一性"""
    link = str(item_link or "").strip()
    if link.startswith("http"):
        return link[:500]
    suffix = md5(title)[:8] if title else md5(source_url)[:8]
    return f"{source_url}#{suffix}"[:500]


def dispatch(
    db: DB,
    uid: str,
    items: Any,
    source_url: str,
    page_hash: str,
    target_types: list[str],
) -> dict[str, int]:
    stats = {"announcements": 0, "recommendations": 0, "adjustments": 0, "skipped": 0}

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

        # ── 校验关键字段 ──────────────────────────────────────────────────
        if not title:
            stats["skipped"] += 1
            continue

        # ── 分发路由 ─────────────────────────────────────────────────────
        if dtype in ("招生简章", "招生公告", "招生目录", "复试分数线", "拟录取名单", "报录比"):
            row = {
                "university_id": uid,
                "title": title[:200],
                "publish_time": pub_time,
                "url": url_key,
                "type": dtype,
                "content": content or None,
                "content_hash": page_hash,
                "last_updated": now_iso,
            }
            if db.upsert_announcement(row):
                stats["announcements"] += 1

        elif dtype == "推免公告":
            # 同时也存一条 announcement，方便前端统一展示
            db.upsert_announcement({
                "university_id": uid,
                "title": title[:200],
                "publish_time": pub_time,
                "url": url_key,
                "type": "推免公告",
                "content": content or None,
                "content_hash": page_hash,
                "last_updated": now_iso,
            })
            row = {
                "university_id": uid,
                "title": title[:200],
                "type": "正式推免",
                "status": "未开始",
                "url": url_key,
                "content": content or None,
                "content_hash": page_hash,
                "last_updated": now_iso,
            }
            if db.upsert_recommendation(row):
                stats["recommendations"] += 1

        elif dtype == "调剂信息":
            major_list = item.get("major") or []
            major_name = (
                major_list[0] if isinstance(major_list, list) and major_list
                else str(major_list or "不限")
            )[:100]
            row = {
                "university_id": uid,
                "major_name": major_name,
                "year": year,
                "requirements": content or None,
                "url": url_key[:300],
                "content_hash": page_hash,
                "last_updated": now_iso,
            }
            if db.upsert_adjustment(row):
                stats["adjustments"] += 1

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


def build_source_urls(website: str, grad_url: Optional[str], name: str) -> list[str]:
    """生成多个候选数据源 URL，越靠前优先级越高"""
    base = (website or "").rstrip("/")
    urls: list[str] = []

    # 优先：AI 在基础爬取阶段已确认的研招页面
    if grad_url and grad_url.startswith("http"):
        urls.append(grad_url)

    # 官网常见研招路径
    for path in _GRAD_PATHS:
        u = f"{base}{path}"
        if u not in urls:
            urls.append(u)

    # 全国研招网搜索（结构化，可靠）
    urls.append(f"https://yz.chsi.com.cn/sch/schInfo.do?searchType=1&keyword={name}")

    return urls


# ── 单所院校增量更新 ──────────────────────────────────────────────────────────
async def update_university(
    session: ClientSession,
    db: DB,
    uni: dict,
    target_types: list[str],
    force: bool,
    sem: asyncio.Semaphore,
) -> dict:
    name = uni["name"]
    uid = uni["id"]
    website = uni.get("website") or ""
    grad_url = uni.get("graduate_url")

    stats = {"name": name, "fetched": 0, "new": 0, "unchanged": 0, "error": None}

    async with sem:
        source_urls = build_source_urls(website, grad_url, name)

        for url in source_urls:
            try:
                # ── 1. Jina Reader 获取页面内容 ──────────────────────────
                content = await jina_fetch(session, url)
                if not content or len(content) < 200:
                    continue
                stats["fetched"] += 1

                page_hash = md5(content)

                # ── 2. 增量判断（对 announcements 表查哈希）────────────
                if not force:
                    existing = db.get_content_hash("announcements", uid, url)
                    if existing == page_hash:
                        stats["unchanged"] += 1
                        log.debug("[%s] 内容未变化，跳过 %s", name, url[-50:])
                        continue

                # ── 3. 通义千问 AI 提取结构化数据 ─────────────────────
                extracted = await qwen_extract(content)
                if not extracted:
                    continue

                # ── 4. 过滤目标类型 + 写库 ──────────────────────────────
                write_stats = dispatch(db, uid, extracted, url, page_hash, target_types)
                written = sum(v for k, v in write_stats.items() if k != "skipped")
                stats["new"] += written

                if written:
                    log.info(
                        "[%s] %s → 写入 %d 条（公告%d 推免%d 调剂%d）",
                        name, url.split("/")[-2] or url[-40:],
                        written,
                        write_stats["announcements"],
                        write_stats["recommendations"],
                        write_stats["adjustments"],
                    )

            except Exception as exc:
                stats["error"] = str(exc)
                log.exception("[%s] 处理 %s 异常: %s", name, url[-60:], exc)

    return stats


# ── 运行摘要 ──────────────────────────────────────────────────────────────────
def print_summary(results: list, season: str, elapsed: float) -> None:
    total = len(results)
    ok = sum(1 for r in results if isinstance(r, dict) and not r.get("error"))
    fetched = sum(r.get("fetched", 0) for r in results if isinstance(r, dict))
    new_items = sum(r.get("new", 0) for r in results if isinstance(r, dict))
    unchanged = sum(r.get("unchanged", 0) for r in results if isinstance(r, dict))
    errors = [r for r in results if isinstance(r, dict) and r.get("error")]

    log.info("=" * 65)
    log.info("季节: %-6s | 院校: %d/%d | 耗时: %.1fs", season, ok, total, elapsed)
    log.info("页面抓取: %d  |  新增/更新: %d  |  跳过(未变): %d",
             fetched, new_items, unchanged)
    if errors:
        log.warning("异常院校 (%d): %s", len(errors), ", ".join(r["name"] for r in errors))
    log.info("=" * 65)


# ── 主入口 ────────────────────────────────────────────────────────────────────
async def main(
    force: bool,
    season_override: Optional[str],
    concurrency: int,
) -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    if not DASHSCOPE_KEY:
        log.error("缺少 DASHSCOPE_API_KEY")
        sys.exit(1)

    season = season_override or detect_season()
    target_types = SEASON_MAP[season]

    log.info("季节: %s | 更新类型: %s | force=%s",
             season, "、".join(target_types), force)

    db = DB()
    universities = db.get_universities()
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
                update_university(session, db, uni, target_types, force, sem)
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
        "--concurrency", type=int, default=4,
        help="同时处理院校数（默认 4，降低可减少 API 费用）",
    )
    args = parser.parse_args()
    asyncio.run(main(
        force=args.force,
        season_override=args.season,
        concurrency=args.concurrency,
    ))

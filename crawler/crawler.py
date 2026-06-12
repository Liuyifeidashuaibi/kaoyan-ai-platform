#!/usr/bin/env python3
"""
985/211/双一流高校数据爬虫
- --mode=full       全量爬取（首次使用）
- --mode=increment  增量更新（默认，仅爬取新增/变更数据）

数据源：
  - 院校基础信息：教育部官网 + 各高校官网
  - 专业目录：各高校研招网（每年9月更新）
  - 分数线：各高校研招网（每年3-4月公布）
  - 公告/推免：各高校研招网公告板块
"""

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from aiohttp import TCPConnector, ClientSession, ClientTimeout
from bs4 import BeautifulSoup
from supabase import create_client, Client

from config import config, USER_AGENTS

# ──────────────────────────────────────────────────────────────────────────────
# 日志配置
# ──────────────────────────────────────────────────────────────────────────────
def setup_logging() -> logging.Logger:
    logger = logging.getLogger("crawler")
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    fh = logging.FileHandler(config.log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


log = setup_logging()


# ──────────────────────────────────────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class UniversityData:
    name: str
    province: str
    city: str
    school_type: str
    level_985: bool = False
    level_211: bool = False
    double_first_class: Optional[str] = None
    logo_url: Optional[str] = None
    intro: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None


@dataclass
class MajorData:
    university_id: str
    college: str
    name: str
    code: str
    degree_type: str       # 学硕 / 专硕
    study_mode: str        # 全日制 / 非全日制
    exam_type: str = "统考"
    enrollment_count: Optional[int] = None
    subject_category: Optional[str] = None
    first_discipline: Optional[str] = None


@dataclass
class ScoreData:
    university_id: str
    major_id: str
    year: int
    total_score: int
    politics_score: int
    english_score: int
    professional1_score: Optional[int] = None
    professional2_score: Optional[int] = None
    line_diff: Optional[int] = None
    national_line: Optional[int] = None


@dataclass
class AnnouncementData:
    university_id: str
    title: str
    publish_time: str      # ISO date string
    url: str
    type: str              # 招生简章 / 招生公告 / 调剂公告 / 推免公告


@dataclass
class RecommendationData:
    university_id: str
    title: str
    type: str              # 夏令营 / 预推免 / 正式推免
    status: str            # 未开始 / 报名中 / 已结束
    url: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# 断点续爬管理
# ──────────────────────────────────────────────────────────────────────────────
class Checkpoint:
    def __init__(self, filepath: str) -> None:
        self.path = Path(filepath)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "completed_universities": [],
            "last_run_time": None,
            "mode": None,
        }

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def mark_done(self, university_name: str) -> None:
        done = set(self._data.get("completed_universities", []))
        done.add(university_name)
        self._data["completed_universities"] = list(done)
        self._data["last_run_time"] = datetime.now().isoformat()
        self.save()

    def is_done(self, university_name: str) -> bool:
        return university_name in set(
            self._data.get("completed_universities", [])
        )

    def get_last_run_time(self) -> Optional[datetime]:
        t = self._data.get("last_run_time")
        if t:
            try:
                return datetime.fromisoformat(t)
            except Exception:
                pass
        return None

    def reset(self) -> None:
        self._data = {
            "completed_universities": [],
            "last_run_time": None,
            "mode": None,
        }
        self.save()


# ──────────────────────────────────────────────────────────────────────────────
# HTTP 客户端（带反爬策略）
# ──────────────────────────────────────────────────────────────────────────────
class AntiDetectSession:
    """封装 aiohttp Session，内置随机 UA、延迟、指数退避重试"""

    RETRY_STATUS_CODES = {429, 503, 502, 500, 504}

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)

    @staticmethod
    def _random_headers(referer: Optional[str] = None) -> dict:
        ua = random.choice(USER_AGENTS)
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    async def get(self, url: str, referer: Optional[str] = None, **kwargs) -> Optional[str]:
        """GET 请求，失败自动重试，成功返回文本"""
        async with self._semaphore:
            for attempt in range(config.max_retries + 1):
                # 随机延迟
                delay = random.uniform(
                    config.request_delay_min, config.request_delay_max
                )
                await asyncio.sleep(delay)

                try:
                    headers = self._random_headers(referer)
                    timeout = ClientTimeout(total=config.request_timeout)
                    async with self._session.get(
                        url, headers=headers, timeout=timeout, **kwargs
                    ) as resp:
                        if resp.status in self.RETRY_STATUS_CODES:
                            wait = min(
                                config.retry_backoff_base ** attempt,
                                config.retry_backoff_max,
                            )
                            log.warning(
                                "HTTP %s for %s, retry %d/%d after %.1fs",
                                resp.status,
                                url,
                                attempt + 1,
                                config.max_retries,
                                wait,
                            )
                            await asyncio.sleep(wait)
                            continue
                        resp.raise_for_status()
                        return await resp.text(errors="replace")

                except asyncio.TimeoutError:
                    wait = min(
                        config.retry_backoff_base ** attempt,
                        config.retry_backoff_max,
                    )
                    log.warning("Timeout %s, retry %d after %.1fs", url, attempt + 1, wait)
                    await asyncio.sleep(wait)
                except aiohttp.ClientError as exc:
                    wait = min(
                        config.retry_backoff_base ** attempt,
                        config.retry_backoff_max,
                    )
                    log.warning("ClientError %s: %s, retry %d", url, exc, attempt + 1)
                    await asyncio.sleep(wait)

            log.error("FAILED after %d retries: %s", config.max_retries, url)
            return None


# ──────────────────────────────────────────────────────────────────────────────
# Supabase 写入层
# ──────────────────────────────────────────────────────────────────────────────
class SupabaseWriter:
    def __init__(self) -> None:
        self._client: Client = create_client(
            config.supabase_url, config.supabase_service_key
        )

    def upsert_university(self, data: UniversityData) -> Optional[str]:
        """写入院校，返回 school_id"""
        try:
            row = asdict(data)
            res = (
                self._client.table("universities")
                .upsert(row, on_conflict="name")
                .execute()
            )
            if res.data:
                return res.data[0]["id"]
        except Exception as exc:
            log.error("upsert_university failed: %s", exc)
        return None

    def upsert_majors(self, majors: list[MajorData]) -> dict[str, str]:
        """批量写入专业，返回 {code+degree_type+study_mode: id} 映射"""
        id_map: dict[str, str] = {}
        for i in range(0, len(majors), config.batch_size):
            batch = majors[i : i + config.batch_size]
            rows = [asdict(m) for m in batch]
            try:
                res = (
                    self._client.table("majors")
                    .upsert(
                        rows,
                        on_conflict="university_id,code,degree_type,study_mode",
                    )
                    .execute()
                )
                for row in res.data or []:
                    key = f"{row['code']}|{row['degree_type']}|{row['study_mode']}"
                    id_map[key] = row["id"]
            except Exception as exc:
                log.error("upsert_majors batch failed: %s", exc)
        return id_map

    def insert_scores(self, scores: list[ScoreData]) -> None:
        """批量写入分数线（忽略唯一冲突）"""
        for i in range(0, len(scores), config.batch_size):
            batch = scores[i : i + config.batch_size]
            rows = [asdict(s) for s in batch]
            try:
                self._client.table("scores").upsert(
                    rows, on_conflict="major_id,year"
                ).execute()
            except Exception as exc:
                log.error("insert_scores batch failed: %s", exc)

    def insert_announcements(self, items: list[AnnouncementData]) -> None:
        for i in range(0, len(items), config.batch_size):
            batch = items[i : i + config.batch_size]
            rows = [asdict(a) for a in batch]
            try:
                self._client.table("announcements").upsert(
                    rows, on_conflict="university_id,url"
                ).execute()
            except Exception as exc:
                log.error("insert_announcements batch failed: %s", exc)

    def insert_recommendations(self, items: list[RecommendationData]) -> None:
        for i in range(0, len(items), config.batch_size):
            batch = items[i : i + config.batch_size]
            rows = [asdict(r) for r in batch]
            try:
                self._client.table("recommendations").upsert(
                    rows, on_conflict="university_id,url"
                ).execute()
            except Exception as exc:
                log.error("insert_recommendations batch failed: %s", exc)

    def get_university_id(self, name: str) -> Optional[str]:
        try:
            res = (
                self._client.table("universities")
                .select("id")
                .eq("name", name)
                .maybe_single()
                .execute()
            )
            return res.data["id"] if res.data else None
        except Exception:
            return None


# ──────────────────────────────────────────────────────────────────────────────
# 解析工具
# ──────────────────────────────────────────────────────────────────────────────
def parse_score(text: str) -> Optional[int]:
    """从字符串提取整数分数"""
    text = text.strip().replace("分", "").replace(",", "")
    try:
        v = int(text)
        return v if 0 < v < 500 else None
    except ValueError:
        return None


def infer_status(start: Optional[str], end: Optional[str]) -> str:
    """根据时间推断状态"""
    today = date.today().isoformat()
    if start and today < start:
        return "未开始"
    if end and today > end:
        return "已结束"
    return "报名中"


# ──────────────────────────────────────────────────────────────────────────────
# 院校爬取逻辑（抽象基类 + 具体实现示例）
# ──────────────────────────────────────────────────────────────────────────────
class UniversityCrawler:
    """
    单所院校爬虫基类。
    子类按院校研招网结构重写 crawl_* 方法。
    对于结构相似的院校，可共用一套逻辑。
    """

    def __init__(
        self,
        session: AntiDetectSession,
        writer: SupabaseWriter,
        university_id: str,
        university_name: str,
        base_url: str,
    ) -> None:
        self.session = session
        self.writer = writer
        self.university_id = university_id
        self.name = university_name
        self.base_url = base_url

    async def crawl_majors(self) -> list[MajorData]:
        """爬取专业目录页面，返回 MajorData 列表"""
        # 通用实现：访问 /yjszs/zsxx/zsjz/ 类型路径
        # 实际生产中需按院校结构定制
        log.debug("[%s] 爬取专业目录...", self.name)
        return []

    async def crawl_scores(self, major_id_map: dict[str, str]) -> list[ScoreData]:
        """爬取历年分数线，返回 ScoreData 列表"""
        log.debug("[%s] 爬取分数线...", self.name)
        return []

    async def crawl_announcements(
        self, last_run_time: Optional[datetime]
    ) -> list[AnnouncementData]:
        """爬取招生公告（增量：仅取 last_run_time 之后的）"""
        log.debug("[%s] 爬取公告...", self.name)
        return []

    async def crawl_recommendations(
        self, last_run_time: Optional[datetime]
    ) -> list[RecommendationData]:
        """爬取推免信息"""
        log.debug("[%s] 爬取推免...", self.name)
        return []

    async def run_full(self) -> None:
        """全量爬取：专业 + 分数 + 公告 + 推免"""
        majors = await self.crawl_majors()
        if majors:
            major_id_map = self.writer.upsert_majors(majors)
            log.info("[%s] 写入 %d 个专业", self.name, len(majors))
        else:
            major_id_map = {}

        scores = await self.crawl_scores(major_id_map)
        if scores:
            self.writer.insert_scores(scores)
            log.info("[%s] 写入 %d 条分数线", self.name, len(scores))

        announcements = await self.crawl_announcements(None)
        if announcements:
            self.writer.insert_announcements(announcements)
            log.info("[%s] 写入 %d 条公告", self.name, len(announcements))

        recommendations = await self.crawl_recommendations(None)
        if recommendations:
            self.writer.insert_recommendations(recommendations)
            log.info("[%s] 写入 %d 条推免", self.name, len(recommendations))

    async def run_increment(self, last_run_time: Optional[datetime]) -> None:
        """增量更新：
        - 专业：每年9月执行；其他月份跳过
        - 分数：每年3-4月执行；其他月份跳过
        - 公告/推免：总是爬取（仅取新内容）
        """
        now = datetime.now()

        # 专业目录：9月更新
        if now.month == 9:
            majors = await self.crawl_majors()
            if majors:
                major_id_map = self.writer.upsert_majors(majors)
                log.info("[%s] 增量更新专业 %d 个", self.name, len(majors))
            else:
                major_id_map = {}
        else:
            major_id_map = {}
            log.debug("[%s] 非9月，跳过专业目录更新", self.name)

        # 分数线：3-4月更新
        if now.month in (3, 4):
            scores = await self.crawl_scores(major_id_map)
            if scores:
                self.writer.insert_scores(scores)
                log.info("[%s] 增量写入分数线 %d 条", self.name, len(scores))
        else:
            log.debug("[%s] 非3-4月，跳过分数线更新", self.name)

        # 公告/推免：每次都爬（按时间增量）
        announcements = await self.crawl_announcements(last_run_time)
        if announcements:
            self.writer.insert_announcements(announcements)
            log.info("[%s] 增量写入公告 %d 条", self.name, len(announcements))

        recommendations = await self.crawl_recommendations(last_run_time)
        if recommendations:
            self.writer.insert_recommendations(recommendations)
            log.info("[%s] 增量写入推免 %d 条", self.name, len(recommendations))


# ──────────────────────────────────────────────────────────────────────────────
# 示例：通用研招网结构爬虫（适用于大多数高校）
# ──────────────────────────────────────────────────────────────────────────────
class GenericYanZhaoCrawler(UniversityCrawler):
    """
    通用研招网爬虫模板。
    适用于以标准表格展示专业目录和分数线的院校。
    """

    MAJOR_TABLE_KEYWORDS = ["专业代码", "专业名称", "招生人数"]
    SCORE_TABLE_KEYWORDS = ["复试分数线", "总分", "政治"]
    ANNOUNCEMENT_KEYWORDS = ["招生简章", "招生公告", "调剂", "推免", "夏令营"]

    async def crawl_majors(self) -> list[MajorData]:
        majors: list[MajorData] = []
        # 构造研招网专业目录 URL（各校路径不同，此处示例）
        candidate_paths = [
            "/yjszs/zsxx/zsjz/",
            "/graduate/admission/major/",
            "/zsxx/sszy/",
            "/yzb/zsxx/",
        ]
        for path in candidate_paths:
            url = urljoin(self.base_url, path)
            html = await self.session.get(url, referer=self.base_url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            parsed = self._parse_major_table(soup)
            if parsed:
                majors.extend(parsed)
                break

        return majors

    def _parse_major_table(self, soup: BeautifulSoup) -> list[MajorData]:
        majors: list[MajorData] = []
        tables = soup.find_all("table")
        for table in tables:
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if not any(kw in " ".join(headers) for kw in self.MAJOR_TABLE_KEYWORDS):
                continue

            # 尝试识别列索引
            col_map = {}
            for i, h in enumerate(headers):
                if "代码" in h:
                    col_map["code"] = i
                elif "名称" in h or "专业" in h:
                    col_map["name"] = i
                elif "学院" in h:
                    col_map["college"] = i
                elif "人数" in h or "招生" in h:
                    col_map["enrollment"] = i
                elif "方式" in h or "全日" in h:
                    col_map["mode"] = i
                elif "类型" in h or "学位" in h:
                    col_map["degree"] = i

            if "code" not in col_map or "name" not in col_map:
                continue

            rows = table.find_all("tr")[1:]  # 跳过表头
            current_college = "未知学院"

            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue

                texts = [c.get_text(strip=True) for c in cells]

                # 检测学院行（colspan 合并行）
                if cells[0].get("colspan"):
                    current_college = texts[0]
                    continue

                code = texts[col_map.get("code", 0)].strip()
                if not code or len(code) < 6:
                    continue

                name = texts[col_map.get("name", 1)].strip()
                college = (
                    texts[col_map.get("college", 0)] if "college" in col_map else current_college
                )
                enrollment_text = texts[col_map.get("enrollment", -1)] if "enrollment" in col_map else ""
                enrollment = parse_score(enrollment_text) if enrollment_text else None

                # 推断学位类型：专业代码085xxx/125xxx/135xxx 通常为专硕
                is_zhuan = code[:3] in {
                    "085", "125", "135", "045", "055", "065", "075", "095", "105",
                }
                degree_type = "专硕" if is_zhuan else "学硕"
                study_mode = texts[col_map.get("mode", -1)].strip() if "mode" in col_map else "全日制"
                if study_mode not in ("全日制", "非全日制"):
                    study_mode = "全日制"

                majors.append(
                    MajorData(
                        university_id=self.university_id,
                        college=college or "未知学院",
                        name=name,
                        code=code,
                        degree_type=degree_type,
                        study_mode=study_mode,
                        enrollment_count=enrollment,
                    )
                )

        return majors

    async def crawl_scores(self, major_id_map: dict[str, str]) -> list[ScoreData]:
        scores: list[ScoreData] = []
        current_year = datetime.now().year

        candidate_paths = [
            "/yjszs/zsxx/fsx/",
            "/graduate/admission/score/",
            "/zsxx/fsxxx/",
        ]
        for path in candidate_paths:
            url = urljoin(self.base_url, path)
            html = await self.session.get(url, referer=self.base_url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            parsed = self._parse_score_table(soup, major_id_map, current_year)
            if parsed:
                scores.extend(parsed)
                break

        return scores

    def _parse_score_table(
        self,
        soup: BeautifulSoup,
        major_id_map: dict[str, str],
        year: int,
    ) -> list[ScoreData]:
        scores: list[ScoreData] = []
        tables = soup.find_all("table")

        for table in tables:
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if not any(kw in " ".join(headers) for kw in self.SCORE_TABLE_KEYWORDS):
                continue

            col_map = {}
            for i, h in enumerate(headers):
                if "专业" in h and "代码" in h:
                    col_map["code"] = i
                elif "总分" in h:
                    col_map["total"] = i
                elif "政治" in h or "思想" in h:
                    col_map["politics"] = i
                elif "英语" in h or "外语" in h:
                    col_map["english"] = i
                elif "业务" in h and "一" in h or "专业课" in h and "一" in h:
                    col_map["pro1"] = i
                elif "业务" in h and "二" in h or "专业课" in h and "二" in h:
                    col_map["pro2"] = i
                elif "年份" in h or "年度" in h:
                    col_map["year"] = i

            if "total" not in col_map:
                continue

            rows = table.find_all("tr")[1:]
            for row in rows:
                cells = row.find_all("td")
                texts = [c.get_text(strip=True) for c in cells]
                if len(texts) < 3:
                    continue

                code = texts[col_map.get("code", 0)].strip()
                total = parse_score(texts[col_map.get("total", 1)])
                politics = parse_score(texts[col_map.get("politics", 2)])
                english = parse_score(texts[col_map.get("english", 3)])
                pro1 = parse_score(texts[col_map.get("pro1", 4)]) if "pro1" in col_map else None
                pro2 = parse_score(texts[col_map.get("pro2", 5)]) if "pro2" in col_map else None
                score_year = int(texts[col_map.get("year", 0)]) if "year" in col_map else year

                if not total or not politics or not english:
                    continue

                # 查找 major_id
                major_id = None
                for key, mid in major_id_map.items():
                    if key.startswith(code + "|"):
                        major_id = mid
                        break

                if not major_id:
                    continue

                scores.append(
                    ScoreData(
                        university_id=self.university_id,
                        major_id=major_id,
                        year=score_year,
                        total_score=total,
                        politics_score=politics,
                        english_score=english,
                        professional1_score=pro1,
                        professional2_score=pro2,
                    )
                )

        return scores

    async def crawl_announcements(
        self, last_run_time: Optional[datetime]
    ) -> list[AnnouncementData]:
        items: list[AnnouncementData] = []
        candidate_paths = [
            "/yjszs/tzgg/",
            "/graduate/news/",
            "/yzb/tzgg/",
            "/zsxx/tzgg/",
        ]
        for path in candidate_paths:
            url = urljoin(self.base_url, path)
            html = await self.session.get(url, referer=self.base_url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            parsed = self._parse_announcement_list(soup, url, last_run_time)
            if parsed:
                items.extend(parsed)
                break

        return items

    def _parse_announcement_list(
        self,
        soup: BeautifulSoup,
        page_url: str,
        last_run_time: Optional[datetime],
    ) -> list[AnnouncementData]:
        items: list[AnnouncementData] = []
        links = soup.find_all("a", href=True)

        for a in links:
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            # 匹配关键词
            matched_type = None
            for kw, t in [
                ("招生简章", "招生简章"),
                ("招生公告", "招生公告"),
                ("调剂", "调剂公告"),
                ("推免", "推免公告"),
                ("夏令营", "推免公告"),
            ]:
                if kw in title:
                    matched_type = t
                    break

            if not matched_type:
                continue

            href = a["href"]
            full_url = urljoin(page_url, href)

            # 尝试从父元素提取日期
            publish_time = date.today().isoformat()
            parent = a.parent
            if parent:
                date_text = parent.get_text(strip=True)
                import re
                m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", date_text)
                if m:
                    y, mo, d = m.groups()
                    publish_time = f"{y}-{int(mo):02d}-{int(d):02d}"

            # 增量过滤
            if last_run_time:
                try:
                    pub_date = datetime.fromisoformat(publish_time)
                    if pub_date <= last_run_time:
                        continue
                except Exception:
                    pass

            items.append(
                    AnnouncementData(
                        university_id=self.university_id,
                    title=title,
                    publish_time=publish_time,
                    url=full_url,
                    type=matched_type,
                )
            )

        return items


# ──────────────────────────────────────────────────────────────────────────────
# 种子数据（985/211 高校列表）
# ──────────────────────────────────────────────────────────────────────────────
SEED_UNIVERSITIES: list[dict] = [
    # 985 + 211
    {"name": "北京大学", "province": "北京", "city": "北京", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.pku.edu.cn"},
    {"name": "清华大学", "province": "北京", "city": "北京", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.tsinghua.edu.cn"},
    {"name": "复旦大学", "province": "上海", "city": "上海", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.fudan.edu.cn"},
    {"name": "上海交通大学", "province": "上海", "city": "上海", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.sjtu.edu.cn"},
    {"name": "浙江大学", "province": "浙江", "city": "杭州", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.zju.edu.cn"},
    {"name": "南京大学", "province": "江苏", "city": "南京", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.nju.edu.cn"},
    {"name": "武汉大学", "province": "湖北", "city": "武汉", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.whu.edu.cn"},
    {"name": "华中科技大学", "province": "湖北", "city": "武汉", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.hust.edu.cn"},
    {"name": "中国科学技术大学", "province": "安徽", "city": "合肥", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.ustc.edu.cn"},
    {"name": "哈尔滨工业大学", "province": "黑龙江", "city": "哈尔滨", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.hit.edu.cn"},
    {"name": "西安交通大学", "province": "陕西", "city": "西安", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.xjtu.edu.cn"},
    {"name": "北京航空航天大学", "province": "北京", "city": "北京", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.buaa.edu.cn"},
    {"name": "北京理工大学", "province": "北京", "city": "北京", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.bit.edu.cn"},
    {"name": "中山大学", "province": "广东", "city": "广州", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.sysu.edu.cn"},
    {"name": "华南理工大学", "province": "广东", "city": "广州", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.scut.edu.cn"},
    {"name": "天津大学", "province": "天津", "city": "天津", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.tju.edu.cn"},
    {"name": "南开大学", "province": "天津", "city": "天津", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.nankai.edu.cn"},
    {"name": "吉林大学", "province": "吉林", "city": "长春", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.jlu.edu.cn"},
    {"name": "东南大学", "province": "江苏", "city": "南京", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.seu.edu.cn"},
    {"name": "厦门大学", "province": "福建", "city": "厦门", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.xmu.edu.cn"},
    {"name": "四川大学", "province": "四川", "city": "成都", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.scu.edu.cn"},
    {"name": "重庆大学", "province": "重庆", "city": "重庆", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.cqu.edu.cn"},
    {"name": "西北工业大学", "province": "陕西", "city": "西安", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.nwpu.edu.cn"},
    {"name": "中国人民大学", "province": "北京", "city": "北京", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.ruc.edu.cn"},
    {"name": "北京师范大学", "province": "北京", "city": "北京", "school_type": "师范",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.bnu.edu.cn"},
    {"name": "同济大学", "province": "上海", "city": "上海", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.tongji.edu.cn"},
    {"name": "华东师范大学", "province": "上海", "city": "上海", "school_type": "师范",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.ecnu.edu.cn"},
    {"name": "大连理工大学", "province": "辽宁", "city": "大连", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.dlut.edu.cn"},
    {"name": "东北大学", "province": "辽宁", "city": "沈阳", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.neu.edu.cn"},
    {"name": "湖南大学", "province": "湖南", "city": "长沙", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.hnu.edu.cn"},
    {"name": "中南大学", "province": "湖南", "city": "长沙", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.csu.edu.cn"},
    {"name": "山东大学", "province": "山东", "city": "济南", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.sdu.edu.cn"},
    {"name": "中国海洋大学", "province": "山东", "city": "青岛", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.ouc.edu.cn"},
    {"name": "兰州大学", "province": "甘肃", "city": "兰州", "school_type": "综合",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.lzu.edu.cn"},
    {"name": "电子科技大学", "province": "四川", "city": "成都", "school_type": "理工",
     "level_985": True, "level_211": True, "double_first_class": "一流大学A",
     "website": "https://www.uestc.edu.cn"},
    {"name": "云南大学", "province": "云南", "city": "昆明", "school_type": "综合",
     "level_985": False, "level_211": True, "double_first_class": "一流大学B",
     "website": "https://www.ynu.edu.cn"},
    {"name": "郑州大学", "province": "河南", "city": "郑州", "school_type": "综合",
     "level_985": False, "level_211": True, "double_first_class": "一流大学B",
     "website": "https://www.zzu.edu.cn"},
    {"name": "新疆大学", "province": "新疆", "city": "乌鲁木齐", "school_type": "综合",
     "level_985": False, "level_211": True, "double_first_class": "一流大学B",
     "website": "https://www.xju.edu.cn"},
    {"name": "贵州大学", "province": "贵州", "city": "贵阳", "school_type": "综合",
     "level_985": False, "level_211": True, "double_first_class": "一流大学B",
     "website": "https://www.gzu.edu.cn"},
    # 以上仅为示例；完整列表请从 universities_seed.json 加载
]


# ──────────────────────────────────────────────────────────────────────────────
# 主控流程
# ──────────────────────────────────────────────────────────────────────────────
async def crawl_university(
    session: AntiDetectSession,
    writer: SupabaseWriter,
    checkpoint: Checkpoint,
    uni_seed: dict,
    mode: str,
) -> None:
    name = uni_seed["name"]

    # 断点续爬：全量模式下跳过已完成的院校
    if mode == "full" and checkpoint.is_done(name):
        log.info("[%s] 已完成，跳过", name)
        return

    log.info("[%s] 开始爬取 (mode=%s)", name, mode)

    # 写入院校基础信息（仅首次 full 模式或院校不存在时）
    university_id = writer.get_university_id(name)
    if not university_id:
        uni_data = UniversityData(
            name=name,
            province=uni_seed["province"],
            city=uni_seed["city"],
            school_type=uni_seed["school_type"],
            level_985=uni_seed.get("level_985", False),
            level_211=uni_seed.get("level_211", False),
            double_first_class=uni_seed.get("double_first_class"),
            website=uni_seed.get("website"),
        )
        university_id = writer.upsert_university(uni_data)
        log.info("[%s] 院校信息写入完成，id=%s", name, university_id)

    if not university_id:
        log.error("[%s] 无法获取 university_id，跳过", name)
        return

    crawler = GenericYanZhaoCrawler(
        session=session,
        writer=writer,
        university_id=university_id,
        university_name=name,
        base_url=uni_seed.get("website", ""),
    )

    try:
        if mode == "full":
            await crawler.run_full()
        else:
            await crawler.run_increment(checkpoint.get_last_run_time())
        checkpoint.mark_done(name)
        log.info("[%s] 爬取完成", name)
    except Exception as exc:
        log.exception("[%s] 爬取异常: %s", name, exc)


async def main(mode: str) -> None:
    config.validate()

    # 加载种子数据
    seed_file = config.universities_list_file
    if seed_file and Path(seed_file).exists():
        with open(seed_file, encoding="utf-8") as f:
            universities = json.load(f)
        log.info("从 %s 加载 %d 所院校", seed_file, len(universities))
    else:
        universities = SEED_UNIVERSITIES
        log.info("使用内置种子数据，共 %d 所院校", len(universities))

    checkpoint = Checkpoint(config.checkpoint_file)

    # 全量模式重置断点
    if mode == "full":
        log.info("全量模式：重置断点")
        checkpoint.reset()

    writer = SupabaseWriter()

    connector = TCPConnector(
        limit=config.max_concurrent_requests,
        limit_per_host=config.max_connections_per_host,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
    )
    timeout = ClientTimeout(total=config.request_timeout)

    async with ClientSession(connector=connector, timeout=timeout) as raw_session:
        session = AntiDetectSession(raw_session)

        semaphore = asyncio.Semaphore(config.max_concurrent_universities)

        async def bounded_crawl(uni: dict) -> None:
            async with semaphore:
                await crawl_university(session, writer, checkpoint, uni, mode)

        tasks = [bounded_crawl(uni) for uni in universities]
        await asyncio.gather(*tasks, return_exceptions=True)

    log.info("所有院校爬取任务完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="985/211 考研数据爬虫")
    parser.add_argument(
        "--mode",
        choices=["full", "increment"],
        default="increment",
        help="full=全量首次爬取，increment=增量更新（默认）",
    )
    args = parser.parse_args()

    # 从 .env 加载环境变量
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

    log.info("启动爬虫，mode=%s", args.mode)
    start = time.time()
    asyncio.run(main(args.mode))
    log.info("总耗时 %.1f 秒", time.time() - start)

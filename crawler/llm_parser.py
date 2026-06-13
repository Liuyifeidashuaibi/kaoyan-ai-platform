"""
通义千问网页解析 — 精简输入、截断、缓存、节流重试。

仅负责大模型调用环节；抓取/入库由 crawl_updates_smart.py 编排。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI

log = logging.getLogger("update.llm")

# 固定解析模型（结构化 JSON 提取，成本低于 qwen-max）
PARSE_MODEL = os.environ.get("CRAWLER_PARSE_MODEL", "qwen-turbo")
FALLBACK_MODEL = os.environ.get("CRAWLER_FALLBACK_MODEL", "qwen-plus")
LONG_MODEL = os.environ.get("CRAWLER_LONG_MODEL", "qwen-long")


def _model_chain(env_key: str, *, prefer_long: bool = False, content_len: int = 0) -> list[str]:
    """按环境变量拼模型链；长文/PDF 时优先 qwen-long。"""
    raw = os.environ.get(env_key, "").strip()
    if raw:
        models = [m.strip() for m in raw.split(",") if m.strip()]
    else:
        models = [PARSE_MODEL]
        if FALLBACK_MODEL and FALLBACK_MODEL != PARSE_MODEL:
            models.append(FALLBACK_MODEL)
        if LONG_MODEL and LONG_MODEL not in models:
            models.append(LONG_MODEL)
    if prefer_long or content_len > 8000:
        if LONG_MODEL in models:
            models = [LONG_MODEL] + [m for m in models if m != LONG_MODEL]
    return list(dict.fromkeys(models))
MAX_INPUT_CHARS = int(os.environ.get("CRAWLER_MAX_INPUT_CHARS", "8000"))
MAX_OUTPUT_TOKENS = int(os.environ.get("CRAWLER_MAX_OUTPUT_TOKENS", "1500"))
PARSE_TEMPERATURE = 0.01
MAX_NETWORK_RETRIES = 2
RETRY_INTERVALS = (5.0, 12.0)

CACHE_FILE = Path(__file__).parent / "parse_cache.json"

# 截断时优先保留含以下关键词的行
_PRIORITY_KEYWORDS = (
    "分数线", "复试", "录取", "招生", "专业", "计划", "人数", "调剂",
    "推免", "简章", "目录", "报录比", "总分", "政治", "英语", "专业课",
    "学院", "学位", "学硕", "专硕", "代码", "年份",
)

# 可删除的导航/页脚类噪音（Markdown / 纯文本）
_NOISE_PATTERNS = [
    re.compile(r"<script[\s\S]*?</script>", re.I),
    re.compile(r"<style[\s\S]*?</style>", re.I),
    re.compile(r"<nav[\s\S]*?</nav>", re.I),
    re.compile(r"<footer[\s\S]*?</footer>", re.I),
    re.compile(r"<header[\s\S]*?</header>", re.I),
    re.compile(r"<aside[\s\S]*?</aside>", re.I),
    re.compile(r"<!--[\s\S]*?-->", re.M),
]
_NOISE_LINE_RE = re.compile(
    r"^(首页|主页|返回|登录|注册|版权|Copyright|友情链接|"
    r"网站地图|分享到|扫一扫|关注我们|上一页|下一页|"
    r"面包屑|Breadcrumb).*$",
    re.I | re.M,
)

EXTRACT_PROMPT = """从网页内容提取考研数据，仅输出标准 JSON，禁止任何解释。
字段：type(招生简章|招生目录|复试分数线|拟录取名单|推免公告|调剂信息|报录比)、school、college、year、title、publish_time(YYYY-MM-DD)、content(摘要≤120字)、major(专业名或代码数组)、major_code(6位字符串)、total_score、politics_score、english_score、professional1_score、professional2_score、line_diff、quota(调剂名额)、contact、link
缺省填null；多条用JSON数组；单条可用JSON对象。
内容：
{clean_html}"""

SCORES_EXTRACT_PROMPT = """你是考研复试分数线提取专家。从以下内容提取 {year} 年硕士研究生复试分数线（院线/校线/复试基本分数线）。
要求：
1. 只提取 type 固定为「复试分数线」的记录
2. 表格中每一行专业都要输出，不要遗漏
3. major_code 必须是6位数字字符串；major 为专业名称
4. total_score=总分，politics_score=政治/政综，english_score=外语，professional1_score=业务课一，professional2_score=业务课二（无则null）
5. 仅输出 JSON 数组，禁止 markdown 与解释文字
{majors_hint}

网页内容：
{clean_html}"""

SCORES_MAX_OUTPUT_TOKENS = int(os.environ.get("CRAWLER_SCORES_MAX_TOKENS", "4000"))
SCORES_MAX_INPUT_CHARS = int(os.environ.get("CRAWLER_SCORES_MAX_INPUT", "12000"))

ADMISSIONS_EXTRACT_PROMPT = """你是考研拟录取名单提取专家。从以下内容提取 {year} 年硕士研究生拟录取/统考录取考生记录。
要求：
1. 只提取 type 固定为「拟录取名单」的记录
2. 表格中每一名拟录取考生都要输出，不要遗漏
3. major_code 必须是6位数字字符串；major 为专业名称；college 为学院名称
4. initial_score=初试总分（必填）；retest_score=复试成绩（无则null）；final_score=综合成绩（无则null）
5. candidate_no=考生编号或序号（无则null）；candidate_name=姓名（无则null）
6. admission_status 固定为「拟录取」
7. 仅输出 JSON 数组，禁止 markdown 与解释文字
{majors_hint}

网页内容：
{clean_html}"""

ADMISSIONS_MAX_OUTPUT_TOKENS = int(os.environ.get("CRAWLER_ADMISSIONS_MAX_TOKENS", "8000"))
ADMISSIONS_MAX_INPUT_CHARS = int(os.environ.get("CRAWLER_ADMISSIONS_MAX_INPUT", "16000"))


_qwen: Optional[AsyncOpenAI] = None


def get_qwen() -> AsyncOpenAI:
    global _qwen
    if _qwen is None:
        key = os.environ.get("DASHSCOPE_API_KEY", "")
        _qwen = AsyncOpenAI(
            api_key=key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    return _qwen


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


def clean_page_content(raw: str) -> str:
    """删除脚本、样式、导航、页脚等噪音，保留正文与表格类信息。"""
    if not raw:
        return ""
    text = raw
    for pat in _NOISE_PATTERNS:
        text = pat.sub("", text)
    # Markdown 链接保留文字
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or len(s) < 2:
            continue
        if _NOISE_LINE_RE.match(s):
            continue
        if re.search(r"(广告|赞助商|cookie|隐私政策|用户协议)", s, re.I):
            continue
        lines.append(s)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def truncate_for_llm(text: str, max_chars: int = MAX_INPUT_CHARS) -> str:
    """超长截断：优先保留含核心考研字段的段落。"""
    if len(text) <= max_chars:
        return text
    lines = text.splitlines()
    priority: list[str] = []
    normal: list[str] = []
    for line in lines:
        if any(kw in line for kw in _PRIORITY_KEYWORDS):
            priority.append(line)
        else:
            normal.append(line)
    merged = priority + normal
    out: list[str] = []
    total = 0
    for line in merged:
        if total + len(line) + 1 > max_chars:
            break
        out.append(line)
        total += len(line) + 1
    return "\n".join(out)


class ParseCache:
    """content_hash → 历史解析结果，避免同内容重复调用大模型。"""

    def __init__(self, path: Path = CACHE_FILE) -> None:
        self.path = path
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def get(self, content_hash: str) -> Optional[Any]:
        return self._data.get(content_hash)

    def set(self, content_hash: str, result: Any) -> None:
        self._data[content_hash] = result
        try:
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            log.error("parse_cache 写入失败: %s", exc)


def _is_network_error(exc: Exception) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError, asyncio.TimeoutError)):
        return True
    msg = str(exc).lower()
    return any(k in msg for k in ("timeout", "connection", "connect", "network"))


async def qwen_extract(
    content: str,
    *,
    cache: Optional[ParseCache] = None,
    content_hash: Optional[str] = None,
) -> Optional[Any]:
    """
    调用通义千问解析网页内容。
    - 空内容 / JSON 解析失败：直接返回 None，不重试
    - 仅网络超时/连接失败时重试，最多 2 次
    """
    cleaned = truncate_for_llm(clean_page_content(content))
    if len(cleaned) < 80:
        return None

    if cache and content_hash:
        cached = cache.get(content_hash)
        if cached is not None:
            return cached

    prompt = EXTRACT_PROMPT.format(clean_html=cleaned)
    last_network_exc: Optional[Exception] = None

    models = _model_chain("CRAWLER_PARSE_MODELS", content_len=len(cleaned))

    for model in models:
        for attempt in range(MAX_NETWORK_RETRIES + 1):
            try:
                resp = await get_qwen().chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=MAX_OUTPUT_TOKENS,
                    temperature=PARSE_TEMPERATURE,
                )
                raw = resp.choices[0].message.content
                result = parse_json_safe(raw)
                if result is None:
                    log.warning("解析结果非 JSON，跳过 model=%s", model)
                    break
                if cache and content_hash:
                    cache.set(content_hash, result)
                return result
            except Exception as exc:
                err = str(exc).lower()
                if "403" in err or "quota" in err or "insufficient" in err:
                    log.warning("模型 %s 额度不足，尝试备用模型", model)
                    break
                if _is_network_error(exc) and attempt < MAX_NETWORK_RETRIES:
                    wait = RETRY_INTERVALS[min(attempt, len(RETRY_INTERVALS) - 1)]
                    log.warning(
                        "Qwen 网络异常，%ds 后重试 (%d/%d): %s",
                        wait,
                        attempt + 1,
                        MAX_NETWORK_RETRIES,
                        exc,
                    )
                    last_network_exc = exc
                    await asyncio.sleep(wait)
                    continue
                if _is_network_error(exc):
                    log.error("Qwen 网络失败（已重试 %d 次）: %s", MAX_NETWORK_RETRIES, exc)
                else:
                    log.error("Qwen 接口/业务异常 model=%s: %s", model, exc)
                break

    if last_network_exc:
        log.error("Qwen 最终失败: %s", last_network_exc)
    return None


async def qwen_extract_scores(
    content: str,
    year: int,
    *,
    majors_hint: str = "",
    cache: Optional[ParseCache] = None,
    content_hash: Optional[str] = None,
) -> Optional[Any]:
    """专用：提取复试分数线 JSON 数组。"""
    cleaned = truncate_for_llm(
        clean_page_content(content),
        max_chars=SCORES_MAX_INPUT_CHARS,
    )
    if len(cleaned) < 80:
        return None

    cache_key = f"scores:{content_hash}" if content_hash else None
    if cache and cache_key:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    hint_block = ""
    if majors_hint.strip():
        hint_block = f"\n6. 本校已知招生专业（优先按 major_code 匹配）：\n{majors_hint.strip()}\n"
    prompt = SCORES_EXTRACT_PROMPT.format(
        year=year,
        clean_html=cleaned,
        majors_hint=hint_block,
    )
    models = _model_chain(
        "CRAWLER_SCORES_MODELS",
        prefer_long=len(cleaned) > 8000,
        content_len=len(cleaned),
    )

    for model in models:
        for attempt in range(MAX_NETWORK_RETRIES + 1):
            try:
                resp = await get_qwen().chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=SCORES_MAX_OUTPUT_TOKENS,
                    temperature=PARSE_TEMPERATURE,
                )
                raw = resp.choices[0].message.content
                result = parse_json_safe(raw)
                if result is None:
                    log.warning("复试线解析非 JSON，跳过 model=%s", model)
                    break
                if isinstance(result, dict):
                    result = [result]
                if cache and cache_key:
                    cache.set(cache_key, result)
                return result
            except Exception as exc:
                err = str(exc).lower()
                if "403" in err or "quota" in err or "insufficient" in err:
                    log.warning("复试线模型 %s 额度不足，尝试备用", model)
                    break
                if _is_network_error(exc) and attempt < MAX_NETWORK_RETRIES:
                    await asyncio.sleep(RETRY_INTERVALS[min(attempt, 1)])
                    continue
                log.error("复试线 Qwen 异常 model=%s: %s", model, exc)
                break
    return None


async def qwen_extract_admissions(
    content: str,
    year: int,
    *,
    majors_hint: str = "",
    cache: Optional[ParseCache] = None,
    content_hash: Optional[str] = None,
) -> Optional[Any]:
    """专用：提取拟录取名单 JSON 数组。"""
    cleaned = truncate_for_llm(
        clean_page_content(content),
        max_chars=ADMISSIONS_MAX_INPUT_CHARS,
    )
    if len(cleaned) < 80:
        return None

    cache_key = f"admissions:{content_hash}" if content_hash else None
    if cache and cache_key:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    hint_block = ""
    if majors_hint.strip():
        hint_block = f"\n8. 本校已知招生专业（优先按 major_code 匹配）：\n{majors_hint.strip()}\n"
    prompt = ADMISSIONS_EXTRACT_PROMPT.format(
        year=year,
        clean_html=cleaned,
        majors_hint=hint_block,
    )
    models = _model_chain(
        "CRAWLER_ADMISSIONS_MODELS",
        prefer_long=len(cleaned) > 8000,
        content_len=len(cleaned),
    )

    for model in models:
        for attempt in range(MAX_NETWORK_RETRIES + 1):
            try:
                resp = await get_qwen().chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=ADMISSIONS_MAX_OUTPUT_TOKENS,
                    temperature=PARSE_TEMPERATURE,
                )
                raw = resp.choices[0].message.content
                result = parse_json_safe(raw)
                if result is None:
                    log.warning("拟录取名单解析非 JSON，跳过 model=%s", model)
                    break
                if isinstance(result, dict):
                    result = [result]
                if cache and cache_key:
                    cache.set(cache_key, result)
                return result
            except Exception as exc:
                err = str(exc).lower()
                if "403" in err or "quota" in err or "insufficient" in err:
                    log.warning("拟录取模型 %s 额度不足，尝试备用", model)
                    break
                if _is_network_error(exc) and attempt < MAX_NETWORK_RETRIES:
                    await asyncio.sleep(RETRY_INTERVALS[min(attempt, 1)])
                    continue
                log.error("拟录取 Qwen 异常 model=%s: %s", model, exc)
                break
    return None

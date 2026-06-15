"""内容抓取器 — HTTP / Playwright。"""



from __future__ import annotations



import hashlib

import logging

import time

from pathlib import Path



import requests

from requests.adapters import HTTPAdapter

from urllib3.util.retry import Retry



log = logging.getLogger("crawler.fetchers")



_HEADERS = {

    "User-Agent": (

        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "

        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    ),

    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",

    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",

}





def _session() -> requests.Session:

    s = requests.Session()

    retry = Retry(

        total=3,

        connect=3,

        read=3,

        backoff_factor=1.2,

        status_forcelist=(429, 500, 502, 503, 504),

        allowed_methods=frozenset(["GET", "HEAD"]),

    )

    adapter = HTTPAdapter(max_retries=retry)

    s.mount("https://", adapter)

    s.mount("http://", adapter)

    return s





def content_hash(text: str | bytes) -> str:

    if isinstance(text, bytes):

        return hashlib.sha256(text).hexdigest()

    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()





def fetch_http(url: str, *, timeout: int = 45, retries: int = 4) -> tuple[str, str]:

    """返回 (html/text, content_hash)。"""

    last_err: Exception | None = None

    sess = _session()

    for attempt in range(retries):

        try:

            resp = sess.get(url, headers=_HEADERS, timeout=timeout)

            resp.raise_for_status()

            resp.encoding = resp.apparent_encoding or "utf-8"

            body = resp.text

            return body, content_hash(body)

        except Exception as exc:

            last_err = exc

            wait = 1.5 * (attempt + 1)

            log.warning("HTTP 抓取失败 (%d/%d) %s: %s", attempt + 1, retries, url, exc)

            time.sleep(wait)

    raise RuntimeError(f"HTTP 抓取失败: {url}") from last_err





def fetch_bytes(url: str, *, timeout: int = 60, retries: int = 4) -> tuple[bytes, str]:

    """下载二进制附件（PDF/Excel 等）。"""

    last_err: Exception | None = None

    sess = _session()

    for attempt in range(retries):

        try:

            resp = sess.get(url, headers=_HEADERS, timeout=timeout)

            resp.raise_for_status()

            data = resp.content

            return data, content_hash(data)

        except Exception as exc:

            last_err = exc

            time.sleep(1.5 * (attempt + 1))

            log.warning("附件下载失败 (%d/%d) %s: %s", attempt + 1, retries, url, exc)

    raise RuntimeError(f"附件下载失败: {url}") from last_err





def fetch_page(url: str, *, prefer_playwright: bool = False) -> tuple[str, str]:
    """智能抓取：.edu.cn 优先 Playwright。"""
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower()
    use_pw = prefer_playwright or host.endswith(".edu.cn") or ".edu.cn" in host

    if use_pw:
        try:
            html, chash = fetch_playwright(url)
            if len(html) >= 200:
                return html, chash
        except Exception as exc:
            log.debug("Playwright 失败，回退 HTTP: %s — %s", url, exc)

    try:
        html, chash = fetch_http(url)
        if len(html) >= 400 or not use_pw:
            return html, chash
    except Exception as exc:
        log.debug("HTTP 失败: %s — %s", url, exc)
        if use_pw:
            return fetch_playwright(url)
        raise

    try:
        return fetch_playwright(url)
    except Exception:
        return html, chash





def fetch_playwright(url: str, *, timeout_ms: int = 60000) -> tuple[str, str]:

    """JS 渲染页面抓取（需安装 playwright）。"""

    try:

        from playwright.sync_api import sync_playwright

    except ImportError as exc:

        raise RuntimeError("未安装 playwright，请执行: pip install playwright && playwright install chromium") from exc



    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        try:

            page = browser.new_page()

            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            page.wait_for_timeout(1500)

            html = page.content()

            return html, content_hash(html)

        finally:

            browser.close()





def _school_slug(school_name: str) -> str:

    """学校目录名：保留中文与字母数字，其余替换为下划线。"""

    import re



    slug = re.sub(r"[^\w\u4e00-\u9fff-]", "_", (school_name or "unknown").strip())

    return slug[:64] or "unknown"





def save_raw(

    raw_root: Path,

    *,

    school_name: str,

    year: int,

    url: str,

    content: str | bytes,

    ext: str = "html",

) -> str:

    """

    保存原始文件到 raw/{school}/{year}/，返回相对 crawler/ 的路径。

    """

    slug = _school_slug(school_name)

    dest_dir = raw_root / slug / str(year)

    dest_dir.mkdir(parents=True, exist_ok=True)

    safe = hashlib.md5(url.encode()).hexdigest()[:16]

    path = dest_dir / f"{safe}.{ext.lstrip('.')}"

    if isinstance(content, bytes):

        path.write_bytes(content)

    else:

        path.write_text(content, encoding="utf-8")

    crawler_root = raw_root.parent if raw_root.name == "raw" else raw_root

    try:

        return str(path.relative_to(crawler_root))

    except ValueError:

        return str(path)



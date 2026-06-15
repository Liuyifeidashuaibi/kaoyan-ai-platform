#!/usr/bin/env python3
"""一次性扫描 zhijiao school_id 并写入缓存。"""
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))

from crawl_basic_once import UNIVERSITIES
from kaoyan_score_sources import (
    fetch_html,
    load_school_id_cache,
    parse_title_school_name,
    save_school_id_cache,
    schoolscore_url,
)

session = requests.Session()
cache = load_school_id_cache()

for sid in range(1, 1501):
    url = schoolscore_url(sid)
    html = fetch_html(session, url, min_delay=0.8, max_delay=1.5)
    if not html or len(html) < 3000:
        continue
    name = parse_title_school_name(html)
    if not name:
        continue
    if name not in cache:
        cache[name] = sid
        print(sid, name)

save_school_id_cache(cache)
targets = {u["name"] for u in UNIVERSITIES}
matched = sum(1 for n in targets if n in cache or any(n in k or k in n for k in cache))
print(f"cache={len(cache)} matched_targets={matched}/{len(targets)}")

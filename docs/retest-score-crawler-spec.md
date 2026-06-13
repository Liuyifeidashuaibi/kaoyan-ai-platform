# 考研专业复试线爬虫方案（2025/2026）

> **用途**：个人学习自用，抓取全国院校分专业真实复试线（初试进入复试最低分，含总分 + 单科线）。  
> **排除**：国家线、34 所自划线校线（`score_level`），只保留学院/专业级 `school_score`。  
> **仓库现状**：核心解析已在 `crawler/kaoyan_score_sources.py`，本方案在其上封装严格串行入口 `crawler/crawl_retest_scores.py`。

---

## 一、核心目标

| 项 | 说明 |
|---|---|
| 年份 | 仅 **2025、2026** |
| 粒度 | 院校 → 学院 → 专业 → 学硕/专硕 |
| 字段 | 总分、政治、英语、业务课一、业务课二 |
| 输出 | **CSV** + **SQLite** 双写，空值填 `无`，同校同专业同年份去重 |

---

## 二、数据源优先级与实测结论

### 1. 首选：掌上考研（kaoyan.cn / zhijiao.cn）

**页面入口（SPA，非静态表格）**

```
https://m.kaoyan.cn/school/{school_id}/score
```

示例（华东师大，**正确 ID 为 261，非 172**）：

```
https://m.kaoyan.cn/school/261/score
```

> ⚠️ `m.kaoyan.cn` 与 `zhijiao.cn` 共用同一套 `school_id`，以 `crawler/data/kaoyan_school_id_map.json` 为准。  
> 172 对应的是另一所院校；华东师大在缓存中为 **261**。

**真实数据接口（推荐，已验证 2025/2026 有数）**

```http
POST https://api.kaoyan.cn/h5/school/schoolScore
Content-Type: application/json
Referer: https://m.kaoyan.cn/
Origin: https://m.kaoyan.cn

{
  "school_id": 261,
  "year": 2025,
  "type": 2,        // 2=学硕, 1=专硕
  "kind": "01",       // 学科门类，见 factor.json
  "page": 1,
  "area": "A"         // A区 / B区
}
```

**元数据（可选，用于缩小 kind 遍历范围）**

```
GET https://static.kaoyan.cn/json/factor/{school_id}/factor.json
```

**响应字段映射**

| API 字段 | 输出字段 |
|---|---|
| `name` | 专业名称 |
| `depart_name` | 学院（`全校或院系` 置空） |
| `degree_type` 1/2 | 专硕/学硕 |
| `total` | 总分线 |
| `politics` | 政治线 |
| `english` | 英语线 |
| `special_one` | 业务课1线 |
| `special_two` | 业务课2线 |
| `data_type` | **仅保留 `school_score`**，丢弃 `score_level`（校线/门类线） |

**兜底：zhijiao 静态 HTML 表格**（2023 年前或 API 无数据时）

```
https://www.zhijiao.cn/kaoyan/web/school/schoolscorelist?school_id={id}&fyear={year}&degree_type={1|2}&area_type=A&page=1
```

解析逻辑见 `kaoyan_score_sources.parse_score_table()`。

**覆盖范围**

- 当前 ID 缓存约 **409** 校（`build_kaoyan_school_ids.py` 可扩至 1500 扫描）
- 2025/2026 实测：华东师大 261 → 2025 年 116 条、2026 年 95 条专业线

---

### 2. 备选1：中国考研网

| 项 | 内容 |
|---|---|
| 主站 | https://www.chinakaoyan.com/ |
| 复试线专区 | https://www.chinakaoyan.com/info/list/ClassID/22.shtml |
| 特点 | 静态页多、按校汇总、反爬弱 |
| 状态 | **仓库尚未实现**，作补源 |

**落地步骤（给 cser）**

1. 列表页抓取各校复试线文章链接（`ClassID/22` 分页）
2. 文章内定位 `<table>`，表头含「总分」「政治」「英语」「业务」
3. 正则提取 `[六位专业代码]专业名`
4. 仅当掌上考研该校 `school_score` 条数为 0 时启用

```python
# 伪代码
if not kaoyan_rows:
    rows = parse_chinakaoyan_article(url, year_filter={2025, 2026})
```

---

### 3. 备选2：中国教育在线（EOL）

| 项 | 内容 |
|---|---|
| 入口 | https://kaoyan.eol.cn/fenshuxian/ |
| 历年索引 | `kaoyan.eol.cn/tiao_ji/wang_nian_fen_shu/index*.shtml` |
| 状态 | 异步解析在 `crawler/score_sources.py`，含国家线过滤 `_NATIONAL_KW` |

作第三顺位补源；优先用已缓存的 `crawler/data/eol_score_index.json`。

---

## 三、技术规范

### 3.1 反爬

```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://m.kaoyan.cn/",
}

# 每次请求前
time.sleep(random.uniform(2.0, 3.0))   # ≥2s，禁止多线程
```

- **禁止** `ThreadPoolExecutor` / `asyncio.gather` 并发抓目标站
- 现有 `crawl_kaoyan_scores_csv.py` 默认并发；本方案用 `crawl_retest_scores.py`（强制串行）

### 3.2 重试

```python
for attempt in range(3):          # 首次 + 最多重试 2 次
    try:
        resp = session.get/post(...)
        if resp.status_code in (403, 404):
            time.sleep(3 * (attempt + 1))
            continue
        ...
    except (Timeout, ConnectionError):
        time.sleep(3 * (attempt + 1))
# 失败写日志，继续下一校
```

### 3.3 解析与清洗

```python
def clean(cell: str) -> str:
    s = re.sub(r"\s+", "", cell or "")
    s = s.replace("—", "").replace("-", "").replace("/", "")
    return s if s else "无"

def parse_score(v) -> str:
    if v is None or v == "":
        return "无"
    return str(int(v)) if str(v).isdigit() else "无"
```

### 3.4 过滤规则

```python
# 1. 只要专业/院线复试线
if item["data_type"] != "school_score":
    continue

# 2. 不要国家线文案
if re.search(r"国家\s*A?\s*区?线|执行国家线", name):
    continue

# 3. 年份白名单
if year not in (2025, 2026):
    continue
```

### 3.5 去重键

```
(年份, 院校名称, 学院, 专业名称, 学硕/专硕)
```

---

## 四、输出规范

### 4.1 CSV 字段（顺序固定）

```
年份,院校名称,学院,专业名称,学硕/专硕,总分线,政治线,英语线,业务课1线,业务课2线,数据来源
```

示例：

```csv
年份,院校名称,学院,专业名称,学硕/专硕,总分线,政治线,英语线,业务课1线,业务课2线,数据来源
2025,华东师范大学,教育学部,教育学,学硕,368,55,55,90,90,kaoyan_h5
2025,华东师范大学,无,学科教学（语文）,专硕,376,55,55,90,90,kaoyan_h5
```

### 4.2 SQLite

**库文件**：`crawler/data/retest_scores.db`

```sql
CREATE TABLE IF NOT EXISTS retest_scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    year          INTEGER NOT NULL,
    university    TEXT    NOT NULL,
    college       TEXT    NOT NULL DEFAULT '无',
    major_name    TEXT    NOT NULL,
    degree_type   TEXT    NOT NULL,          -- 学硕 | 专硕
    total_score   TEXT    NOT NULL DEFAULT '无',
    politics      TEXT    NOT NULL DEFAULT '无',
    english       TEXT    NOT NULL DEFAULT '无',
    pro1          TEXT    NOT NULL DEFAULT '无',
    pro2          TEXT    NOT NULL DEFAULT '无',
    source        TEXT,
    created_at    TEXT    DEFAULT (datetime('now','localtime')),
    UNIQUE (year, university, college, major_name, degree_type)
);

CREATE INDEX IF NOT EXISTS idx_retest_univ_year
    ON retest_scores (university, year);
```

写入使用 `INSERT OR REPLACE`。

---

## 五、目录与文件

```
crawler/
├── kaoyan_score_sources.py      # 掌上考研 API + HTML 解析（已有）
├── crawl_retest_scores.py       # 本方案入口：串行、CSV+SQLite（新增）
├── build_kaoyan_school_ids.py   # 扫描补全 school_id 缓存
├── score_sources.py             # EOL 备选源（已有）
├── data/
│   ├── kaoyan_school_id_map.json
│   ├── retest_scores_2025_2026.csv
│   └── retest_scores.db
└── logs/
    └── retest_scores.log
```

---

## 六、运行命令

```bash
cd crawler
pip install requests beautifulsoup4 lxml

# 试跑 3 校
python crawl_retest_scores.py --limit 3

# 指定学校
python crawl_retest_scores.py --school 华东师范大学

# 全量（串行，约 409 校 × 2 年 × ~15 kind ≈ 数小时）
python crawl_retest_scores.py

# 断点续跑
python crawl_retest_scores.py --offset 50

# 自定义输出路径
python crawl_retest_scores.py --csv data/out.csv --db data/out.db
```

**预估耗时**（串行 2.5s/请求）：

- 单校单年：约 30 次 POST ≈ 75s
- 409 校 × 2 年 ≈ **17–24 小时**（可 `--offset` 分批）

---

## 七、主流程（伪代码）

```python
school_map = load_json("data/kaoyan_school_id_map.json")
session = requests.Session()

for name, school_id in school_map.items():
    for year in (2025, 2026):
        rows = fetch_h5_school_scores(session, school_id, year)
        if not rows:
            rows = fetch_zhijiao_html_fallback(session, school_id, year)
        # if not rows: rows = fetch_chinakaoyan_fallback(name, year)

        for r in rows:
            if r["data_type"] != "school_score":
                continue
            record = normalize(r, university=name)
            buffer.append(record)

    polite_sleep(2, 3)

buffer = dedupe(buffer)
write_csv(buffer, "data/retest_scores_2025_2026.csv")
write_sqlite(buffer, "data/retest_scores.db")
```

---

## 八、验收清单

- [ ] 随机抽 5 校，与掌上考研网页人工比对 3 个专业总分/单科
- [ ] 华东师大 261：2025 ≥ 100 条 `school_score`
- [ ] CSV / SQLite 行数一致
- [ ] 无 `score_level`、无「国家线」文案
- [ ] 重复跑同一命令，SQLite `UNIQUE` 不膨胀
- [ ] 日志中 403/404 校有记录且整体不中断

---

## 九、已知问题与修正

| 问题 | 处理 |
|---|---|
| 用户文档写华东师大 ID=172 | **修正为 261**（172 为其他院校） |
| 页面写「静态 HTML 表格」 | m 站为 SPA，**必须走 H5 API**；HTML 仅 zhijiao 兜底 |
| `factor.json` 年份只列到 2024 | 不影响；直接 POST `year=2025/2026` 仍有数据 |
| 学院字段缺失 | API `depart_name` 为空时填 `无`；可用 zhijiao `schooldepart` 补全 |
| 全量校数 | 先跑缓存 409 校；`build_kaoyan_school_ids.py` 扩 ID 后再跑 |

---

## 十、依赖

```
requests>=2.31.0
beautifulsoup4>=4.12.3
lxml>=5.2.1
```

无需 Supabase / OpenAI（与 `import_kaoyan_scores_csv.py` 导入链路解耦）。

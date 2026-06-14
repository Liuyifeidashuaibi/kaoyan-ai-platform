# 考研择校数据中心

生产级择校数据采集与入库系统，覆盖 985 / 211 / 双一流院校（147 所）。

## 架构

```
crawler/
├── kaoyan-cn/          # 掌上考研 Node 爬虫（双一流 147 校，主数据源）
│   ├── src/            # 抓取 / 增量同步 / 指纹检测
│   └── scripts/        # crawl / sync / verify
├── import_kaoyan_full.py  # JSON → Supabase 入库
├── sync_kaoyan_cn.py      # 一键：抓取 + 入库 + 通知前端
├── discover/           # 研究生院官方来源发现（拟录取/复试线）
├── fetchers/           # HTTP + Playwright 抓取
├── parsers/            # HTML / PDF / Word / Excel 解析
├── ai_extract/         # 千问结构化抽取
├── adapters/           # 学校专属适配器
├── storage/            # Supabase 入库 + Hash 检测
└── main.py             # 官方来源爬虫入口（辅助）
```

### 掌上考研数据流（主路径）

```
kaoyan.cn API
  → crawler/kaoyan-cn (Node 20+)
  → crawler/data/kaoyan-cn/latest/
  → import_kaoyan_full.py
  → Supabase (universities / majors / scores)
  → 前端 /schools 自动刷新
```

### 数据分层



| 层级 | 存储 | 说明 |

|------|------|------|

| Layer1 | `crawler/raw/{学校}/{年份}/` | HTML/PDF/Excel 永久归档 |

| Layer2 | `admission_records` | 逐考生拟录取记录 |

| Layer3 | `major_statistics` | 最低/平均/最高录取分统计 |



### Supabase 表



| 规范表名 | 实际表 |

|---------|--------|

| schools | `universities` + 视图 `schools` |

| colleges | `colleges` |

| majors | `majors` |

| score_lines | `scores` + 视图 `score_lines` |

| admission_records | `admission_records` |

| major_statistics | `major_statistics` |

| source_pages | `source_pages` |

| school_sources | `school_sources` |

| crawl_tasks | `crawl_tasks` |



## 快速开始

```bash
# 1. 配置环境变量（项目根 .env.local 或 crawler/.env）
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...

# 2. 安装依赖
pip install -r crawler/requirements.txt
npm install --prefix crawler/kaoyan-cn

# 3. 一键同步掌上考研数据（抓取 + 入库 + 通知前端）
npm run crawler:kaoyan:sync

# 仅导入已有 JSON（不抓取）
python crawler/sync_kaoyan_cn.py --import-only

# 全量抓取（首次或重建）
python crawler/sync_kaoyan_cn.py --full
```

### 官方来源爬虫（辅助，需 DASHSCOPE_API_KEY）



# 7. 从拟录取记录重算统计

python crawler/main.py recompute-stats

```



## 数据来源优先级



1. **P0** 研究生院/学院官网 — 拟录取名单、拟录取公示

2. **P1** 复试名单、复试成绩公示

3. **P2** 招生目录、招生简章



AI 仅负责结构化抽取，不用于网页发现。



## 后端 API



启动 FastAPI 后可用：



- `GET /api/schools?page=&keyword=&tag=`

- `GET /api/schools/{id}`

- `GET /api/majors?page=&school=&college=&keyword=`

- `GET /api/majors/{id}`

- `GET /api/statistics?school=&college=&major=&year=`

- `GET /api/admissions?school=&college=&major=&year=`

- `GET /api/score-lines?school=&college=&major=&year=`



## 前端



- `/choose-school` → 重定向至 `/schools`

- 院校详情页默认展示 **真实上岸线**（最低录取分），复试线单独 Tab



## 定时任务



GitHub Actions：`.github/workflows/choose-school-crawler.yml`



| 调度 | 模式 | 说明 |

|------|------|------|

| 每日 02:00（北京） | `update` | 增量更新 |

| 每周一 03:00（北京） | `full` | 全量扫描 |

| 每月 1 日 | `recompute-stats` | 统计校验 |



## 日志与归档



- `crawler/logs/crawler.log` — 运行日志

- `crawler/logs/failed_tasks.json` — 失败任务队列

- `crawler/raw/{学校}/{年份}/` — 原始页面/附件存档（可追溯）



## 验收清单



- [x] TOP50 优先校自动发现拟录取来源页

- [x] AI 抽取拟录取名单并计算最低录取分

- [x] 学校-学院-专业关系树（majors + colleges）

- [x] 原始文件归档 raw/{school}/{year}/

- [x] 每日增量 / 每周全量 CI

- [x] 前端 `/schools` 查询真实上岸线

- [x] REST API 可调用

- [x] 每条数据保留 source_url / publish_date / raw_file_path


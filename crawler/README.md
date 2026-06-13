# 考研择校数据中心



生产级择校数据采集与入库系统，覆盖 985 / 211 / 双一流院校。



## 架构



```

crawler/

├── discover/       # 研究生院/学院链接发现（拟录取/复试线/专业目录）

├── fetchers/       # HTTP + Playwright 抓取 + 原始文件归档

├── parsers/        # HTML / PDF / Word / Excel 解析

├── ai_extract/     # 千问结构化抽取（仅解析，不发现）

├── adapters/       # 学校专属适配器（TOP50 优先）

├── schedulers/     # 失败任务队列（JSON + crawl_tasks 表）

├── storage/        # Supabase 入库 + Hash 检测 + 统计聚合

├── raw/            # Layer1 原始数据 raw/{学校}/{年份}/

└── main.py         # 统一入口

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

# 1. 配置环境变量（项目根 .env 或 crawler/.env）

SUPABASE_URL=...

SUPABASE_SERVICE_ROLE_KEY=...

DASHSCOPE_API_KEY=...   # 千问 AI 抽取



# 2. 安装依赖

bash scripts/deploy-choose-school.sh



# 3. 执行数据库迁移（Supabase SQL Editor 或 supabase db push）

#    007_choose_school_datacenter.sql

#    009_admission_datacenter.sql



# 4. 全量更新（复试线 CSV + TOP50 拟录取发现）

python crawler/main.py full



# 5. 增量更新（Hash 检测变更页）

python crawler/main.py update



# 6. 单校更新

python crawler/main.py school 北京大学



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


# 择校数据发布（掌上考研 → Supabase）

择校 UI 数据**只来自掌上考研（kaoyan.cn）**，分三个本机目录协作：

| 目录 | 作用 |
|------|------|
| `E:\Kaoyan\clawer` | **爬虫**：抓掌上考研，你自行运行/定时 |
| `E:\Kaoyan\re` | **数据**：JSON 输出（`latest\syl-schools-full.json`） |
| 本项目 `crawler/` | **发布**：读 `re` → 写入 Supabase → 网站刷新 |

```
掌上考研 (kaoyan.cn)
       ↓  clawer 抓取
E:\Kaoyan\re\latest\
       ↓  本仓库 import
Supabase (universities / majors / scores)
       ↓
前端 /choose-school
```

## 日常用法

### 每日自动（爬取 + 自动上网站）

任选其一：

- 双击 `E:\Kaoyan\clawer\daily-sync-and-publish.bat`
- 或常驻 `E:\Kaoyan\clawer\start-scheduler.bat`（每天 0:00 北京时：sync + 自动发布）

### 手动爬取（只更新 re，不上网站）

双击 `E:\Kaoyan\clawer\sync-now.bat`

### 手动发布到网站

爬取完成后，在项目根目录：

```bash
npm run crawler:kaoyan:import
```

或双击 `scripts\publish-schools.bat`

## 环境变量

见 [.env.example](./.env.example)。必填：

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `KAOYAN_DATA_DIR`（默认 `E:\Kaoyan\re`）

## 本仓库脚本

| 脚本 | 说明 |
|------|------|
| `sync_kaoyan_cn.py` | 发布入口（默认 `--import-only`） |
| `import_kaoyan_full.py` | JSON → Supabase 全量 upsert |
| `audit_kaoyan_scores.py` | 分数覆盖率审计 |
| `fill_low_coverage_scores.py` | 低覆盖院校 H5 补分（可选） |
| `cleanup_duplicate_majors.py` | 删除 DB 内唯一键重复专业 |
| `cleanup_orphan_majors.py` | 删除不在最新 JSON 中的孤儿专业 |
| `verify_majors_json.py` | 发布前 JSON 对照校验 |
| `notify_frontend.py` | 递增 `schools_sync_meta.revision` |

## 前端

入库后自动 `bump_schools_sync()`，前端约 30 秒内刷新，**无需重新部署 Vercel**。

## 数据文件（在 E:\Kaoyan\re）

| 路径 | 说明 |
|------|------|
| `latest/syl-schools-full.json` | 147 校完整详情（入库用） |
| `latest/schools.json` | 院校简表 |
| `logs/changes-*.json` | 增量变更报告 |
| `history/YYYY-MM-DD/` | 按日归档 |

爬虫详细说明见 `E:\Kaoyan\clawer\README.md`。

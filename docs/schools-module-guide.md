# 择校模块 - 完整部署与维护手册

## 一、项目结构说明

```
kaoyan-ai-platform/
├── supabase/
│   └── migrations/
│       ├── 003_choose_school.sql      # 择校模块基础表
│       └── 004_schools_extensions.sql # 扩展（调剂表等）
├── src/
│   ├── lib/api/schools.ts             # Supabase 查询
│   └── app/(main)/schools/            # 择校 UI（/schools）
└── crawler/                           # 仅发布：re → Supabase
    ├── sync_kaoyan_cn.py              # 发布入口
    ├── import_kaoyan_full.py          # JSON 全量入库
    ├── audit_kaoyan_scores.py         # 分数覆盖率审计
    ├── fill_low_coverage_scores.py    # 低覆盖补分（可选）
    ├── paths.py                       # 默认 E:\Kaoyan\re
    └── requirements.txt
```

**三目录协作**（爬虫与数据在本机独立目录）：

| 目录 | 作用 |
|------|------|
| `E:\Kaoyan\clawer` | 抓取掌上考研，写 JSON |
| `E:\Kaoyan\re` | 数据落地（`latest\syl-schools-full.json`） |
| 本仓库 `crawler/` | 读 `re` → Supabase → 网站刷新 |

---

## 二、Supabase 数据库建表

### 步骤 1：启用 pg_trgm 扩展（可选）

Dashboard → Database → Extensions → 搜索 `pg_trgm` → 启用

### 步骤 2：执行迁移

```bash
npm run db:migrate:007
npm run db:migrate:008
```

或在 Dashboard SQL 编辑器依次执行 `supabase/migrations/` 下对应文件。

### 步骤 3：验证表

确认存在：`universities`、`majors`、`scores`、`recommendations`、`adjustments`

---

## 三、配置与发布数据

择校数据**只来自掌上考研**，由 `E:\Kaoyan\clawer` 抓取，本仓库**不负责爬取**。

### 步骤 1：准备环境

```bash
pip install -r crawler/requirements.txt
cp crawler/.env.example crawler/.env
# 填入 SUPABASE_URL、SUPABASE_SERVICE_ROLE_KEY
# 可选 KAOYAN_DATA_DIR=E:\Kaoyan\re
```

### 步骤 2：首次全量抓取（在 clawer 目录）

```bat
E:\Kaoyan\clawer\install.bat
E:\Kaoyan\clawer\crawl-now.bat
```

### 步骤 3：发布到网站

```bash
npm run crawler:kaoyan:import
```

或双击 `scripts\publish-schools.bat`

入库后自动递增 `schools_sync_meta.revision`，前端约 30 秒内刷新。

### 日常更新

| 场景 | 操作 |
|------|------|
| 每日自动（爬取 + 上网站） | `clawer\daily-sync-and-publish.bat` 或 `start-scheduler.bat` |
| 只爬数据（不上网站） | `clawer\sync-now.bat` |
| 手动发布 | `npm run crawler:kaoyan:import` |

爬虫详细说明见 `E:\Kaoyan\clawer\README.md`，发布说明见 [crawler/README.md](../crawler/README.md)。

---

## 四、运行前端项目

根目录 `.env.local`：

```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx
```

```bash
npm run dev
```

访问 `http://localhost:3000/schools`

---

## 五、数据维护

### 分数审计

```bash
python crawler/audit_kaoyan_scores.py
python crawler/audit_kaoyan_scores.py --school 北京大学 --min-coverage 50
```

报告输出：`crawler/logs/audit_scores_report.json`

### 低覆盖补分（可选）

```bash
python crawler/fill_low_coverage_scores.py --dry-run
python crawler/fill_low_coverage_scores.py --school 中央音乐学院
```

### 年度更新节奏

| 时间 | 内容 |
|------|------|
| 每日 | clawer 增量探测 + 可选自动发布 |
| 9–10 月 | 招生简章、专业目录更新 |
| 3–4 月 | 复试分数线更新 |

---

## 六、常见问题

### Q1：页面显示「暂无数据」

1. Supabase 各表是否有数据
2. 全局筛选是否过滤掉所有院校
3. 浏览器控制台 API 报错

### Q2：`SUPABASE_URL 环境变量未设置`

确认 `crawler/.env` 或根 `.env.local` 已配置。

### Q3：发布失败，找不到 JSON

确认 `E:\Kaoyan\re\latest\syl-schools-full.json` 存在；先运行 `clawer\sync-now.bat` 或 `crawl-now.bat`。

### Q4：某校专业数为 0

检查 `re\latest\syl-schools-full.json` 中该校 `plans.items`；重新抓取后 `npm run crawler:kaoyan:import`。

### Q5：RLS 导致无法写入

发布脚本使用 `SUPABASE_SERVICE_ROLE_KEY`（绕过 RLS），不要用 anon key。

### Q6：分数线线差为空

源数据无 `diff_total` 时 `line_diff` 为空，可在 Supabase 手动补全。

---

## 七、性能建议

1. 按需添加 `gin_trgm` 索引（见迁移文件注释）
2. 高频查询可用 Next.js `cache()` / `unstable_cache()`
3. 院校 logo 放 Supabase Storage + CDN

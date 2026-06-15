# 择校模块 - 完整部署与维护手册

## 一、项目结构说明

```
kaoyan-ai-platform/
├── supabase/
│   └── migrations/
│       ├── 003_choose_school.sql      # 择校模块基础表（已存在）
│       └── 004_schools_extensions.sql # 择校模块扩展（新增调剂表+学科分类）
├── src/
│   ├── types/database.ts              # TypeScript 类型（已扩展）
│   ├── lib/api/schools.ts             # Supabase 数据查询工具函数
│   ├── app/(main)/schools/
│   │   ├── page.tsx                   # 择校主页（路由：/schools）
│   │   ├── _context/
│   │   │   └── schools-filter-context.tsx  # 全局 985/211/双一流筛选状态
│   │   ├── _components/
│   │   │   ├── schools-page-client.tsx     # 主页客户端组件
│   │   │   ├── global-filter-drawer.tsx    # 全局筛选弹窗
│   │   │   ├── school-list-view.tsx        # 按学校分类视图
│   │   │   └── major-list-view.tsx         # 按专业分类视图
│   │   └── [universityId]/
│   │       ├── page.tsx                    # 院校详情页
│   │       └── _components/
│   │           ├── university-detail-client.tsx  # 详情主组件
│   │           ├── overview-tab.tsx              # 概况标签
│   │           ├── majors-tab.tsx                # 专业标签
│   │           └── scores-tab.tsx                # 分数线标签
│   └── components/schools/
│       ├── university-card.tsx         # 院校卡片（全局复用）
│       ├── tab-nav.tsx                 # 横向标签导航
│       ├── bottom-filter-sheet.tsx     # 底部筛选面板
│       ├── empty-state.tsx             # 空状态组件
│       └── skeleton-list.tsx           # 骨架屏组件
└── crawler/
    ├── config.py                       # 爬虫配置
    ├── crawler.py                      # 主爬虫逻辑
    ├── requirements.txt                # Python 依赖
    └── .env.example                    # 环境变量示例
```

---

## 二、Supabase 数据库建表

### 步骤 1：启用 pg_trgm 扩展（可选，用于全文搜索）

1. 打开 [Supabase Dashboard](https://supabase.com/dashboard)
2. 进入项目 → Database → Extensions
3. 搜索 `pg_trgm`，点击启用

### 步骤 2：执行迁移 SQL

**方式 A：Supabase CLI（推荐）**
```bash
npx supabase db push
```

**方式 B：Dashboard SQL 编辑器**
1. 打开 Dashboard → SQL Editor
2. 先执行 `supabase/migrations/003_choose_school.sql`（如果尚未执行）
3. 再执行 `supabase/migrations/004_schools_extensions.sql`（新增扩展）
4. 点击 Run 执行

### 步骤 3：验证建表成功

在 Dashboard → Table Editor 中确认以下表已创建：
- `universities` - 院校主表
- `majors` - 专业表
- `scores` - 分数线表
- `recommendations` - 推免信息表
- `adjustments` - 调剂信息表

> 注：`announcements` 表仍存在于历史迁移中，但择校前端已不再展示公告数据。

---

## 三、配置与运行爬虫

### 步骤 1：准备环境

```bash
cd crawler
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 步骤 2：配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入以下值：
# SUPABASE_URL=https://xxx.supabase.co
# SUPABASE_SERVICE_ROLE_KEY=xxx（从 Dashboard > Settings > API > service_role 获取）
```

> **安全提示**：`service_role` key 具有完整数据库写入权限，请勿提交到 Git！

### 步骤 3：首次全量爬取

```bash
# 全量模式：爬取所有院校基础信息 + 专业 + 分数线
python crawler.py --mode=full
```

首次运行约需 2-6 小时（取决于网络状况）。
- 支持中断续爬：直接重新运行即可从断点继续
- 日志写入 `crawler.log`，可实时查看

### 步骤 4：后续增量更新

```bash
# 默认增量模式：仅爬取新增/变更数据
python crawler.py --mode=increment
# 或直接
python crawler.py
```

---

## 四、运行前端项目

### 步骤 1：确保 Supabase 环境变量已配置

在项目根目录的 `.env.local` 中：
```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx
```

### 步骤 2：启动开发服务器

```bash
npm run dev
```

访问 `http://localhost:3000/schools` 即可看到择校模块。

---

## 五、GitHub Actions 自动定时更新

在 `.github/workflows/schools-crawler.yml` 中创建以下工作流：

```yaml
name: 择校数据定时更新

on:
  schedule:
    # 每年3月1日至4月30日 每天早8点运行（分数线更新期）
    - cron: '0 0 1-30 3,4 *'
    # 每年9月1日至10月31日 每天早8点运行（专业目录更新期）
    - cron: '0 0 1-31 9,10 *'
    # 全年每周三早8点运行（数据增量更新）
    - cron: '0 0 * * 3'
  workflow_dispatch:
    inputs:
      mode:
        description: '爬取模式'
        required: true
        default: 'increment'
        type: choice
        options: [full, increment]

jobs:
  crawl:
    runs-on: ubuntu-latest
    timeout-minutes: 360  # 最长6小时

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
          cache-dependency-path: crawler/requirements.txt

      - name: Install dependencies
        run: pip install -r crawler/requirements.txt
        working-directory: crawler

      - name: Run crawler
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          MODE="${{ github.event.inputs.mode || 'increment' }}"
          python crawler.py --mode=$MODE
        working-directory: crawler

      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: crawler-logs-${{ github.run_id }}
          path: crawler/crawler.log
          retention-days: 30
```

### 配置 Secrets

1. GitHub 仓库 → Settings → Secrets and variables → Actions
2. 新增两个 secret：
   - `SUPABASE_URL`：你的 Supabase 项目 URL
   - `SUPABASE_SERVICE_ROLE_KEY`：service_role 密钥

---

## 六、数据维护手册

### 年度更新时间表

| 时间 | 更新内容 | 操作 |
|------|----------|------|
| **每年 9-10 月** | 各院校发布次年招生简章和专业目录 | 自动（GitHub Actions）|
| **每年 3-4 月** | 各院校公布当年复试分数线 | 自动（GitHub Actions）|
| **全年持续** | 院校/专业/学院/复试线增量更新 | 每周自动（GitHub Actions）|
| **按需** | 手动添加/修正院校信息 | Supabase Dashboard |

### 手动维护操作

#### 添加新院校
在 Supabase Dashboard → SQL Editor 执行：
```sql
INSERT INTO universities (name, province, city, school_type, level_985, level_211, double_first_class, website)
VALUES ('院校名称', '省份', '城市', '综合', false, true, '一流学科', 'https://xxx.edu.cn');
```

#### 修正分数线数据
```sql
UPDATE scores
SET total_score = 360, politics_score = 55, english_score = 55
WHERE major_id = 'xxx' AND year = 2025;
```

#### 添加 logo

爬虫默认不爬取 logo（节省带宽）。推荐在 Supabase Storage 中：
1. 创建 `university-logos` bucket（公开读取）
2. 上传 `{university_name}.png` 格式的 logo
3. 在 Supabase Dashboard 批量更新 `logo_url` 字段

---

## 七、常见问题排查

### Q1：页面显示"暂无数据"
**原因**：数据库中还没有数据，或全局筛选过滤掉了所有院校。

**排查**：
1. 检查 Supabase Dashboard 中各表是否有数据
2. 点击右上角筛选图标，确认至少勾选一个层次
3. 检查浏览器控制台是否有 API 报错

### Q2：爬虫报 `SUPABASE_URL 环境变量未设置`
确认 `crawler/.env` 文件存在且格式正确（无引号、无多余空格）。

### Q3：爬虫报 `403 Forbidden` 或 `429 Too Many Requests`
部分院校有防爬措施：
- 检查 `config.py` 中的 `request_delay_min`，调大到 3-5 秒
- 对特定院校降低 `max_connections_per_host` 到 1

### Q4：某院校专业数量为 0
该院校研招网结构与通用模板不兼容，需要为其编写专属爬虫子类：
```python
class PKUCrawler(GenericYanZhaoCrawler):
    """北京大学专属爬虫"""
    async def crawl_majors(self) -> list[MajorData]:
        # 按北京大学研招网实际结构实现
        ...
```

### Q5：RLS 策略导致无法写入
爬虫使用 `service_role` key，会绕过 RLS。确认使用的是 `SUPABASE_SERVICE_ROLE_KEY` 而不是 `anon` key。

### Q6：分数线显示线差为空
线差 `line_diff` 需要知道当年国家线才能计算。可在爬取后手动执行 SQL 更新：
```sql
-- 设置 2025 年工学国家线为 270
UPDATE scores s
SET line_diff = s.total_score - 270,
    national_line = 270
FROM majors m
WHERE s.major_id = m.id
  AND s.year = 2025
  AND m.subject_category = '工学';
```

---

## 八、性能优化建议

1. **Supabase 添加索引**：如果查询慢，在 Dashboard → SQL Editor 执行迁移文件中注释的 `gin_trgm` 索引
2. **前端缓存**：使用 Next.js `cache()` 或 `unstable_cache()` 对高频查询进行服务端缓存
3. **分页加载**：院校数量超过 500 后建议在 API 层加入 `.range()` 分页
4. **图片 CDN**：将院校 logo 存入 Supabase Storage 并开启 CDN 加速

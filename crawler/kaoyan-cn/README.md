# 掌上考研 · 双一流院校数据爬虫

自动抓取 [掌上考研](https://www.kaoyan.cn/school-list/0-0-syl) **147 所双一流院校**的：

- **学校概况**（简介、排名、硕博点、官网电话等）
- **招生计划**（2026 年各专业招生人数、院系等）
- **历年分数**（2022–2026 年复试分数线）

数据保存在 `E:\Kaoyan\re`，爬虫代码在 `E:\Kaoyan\clawer`（本项目）。

---

## 快速开始（只需记住这个）

| 场景 | 做什么 |
|------|--------|
| 第一次用 | 按下方「首次安装」走一遍 |
| **平时 / 隔几天** | **双击 `sync-now.bat`** |
| 看官方有没有更新 | 打开 `E:\Kaoyan\re\logs\changes-日期.json` |

---

## 四个 `.bat` 文件说明

| 文件 | 干什么 | 多久用一次 |
|------|--------|------------|
| **`install.bat`** | 安装 Node 依赖（`npm install`） | 仅首次或换电脑 |
| **`crawl-now.bat`** | **全量抓取** 147 校全部详情 | 仅首次；或数据损坏时 |
| **`sync-now.bat`** | **增量检测**：官方有变才更新 | **日常推荐**，隔几天双击 |
| **`start-scheduler.bat`** | 后台定时，每天北京时间 0:00 自动 sync | 可选；窗口需一直开着 |

> 日常不要点 `crawl-now.bat`，那个会重下全部 79MB 数据，约 4 分钟。  
> 日常点 **`sync-now.bat`** 即可，官方没更新也会告诉你「无变化 147」。

---

## 首次安装（只做一次）

1. 确认已安装 [Node.js 20+](https://nodejs.org/)
2. 双击 **`install.bat`**（装依赖，完成后按任意键关闭）
3. 双击 **`crawl-now.bat`**（全量抓取，约 **4 分钟**，不要关窗口）
4. 在项目文件夹打开命令行，执行：

   ```bat
   cd /d E:\Kaoyan\clawer
   npm run manifest
   npm run verify
   ```

5. 看到 `结论: 数据完整，任务成功 ✓` 即安装完成

---

## 日常使用

### 方式一：手动（推荐）

隔几天双击一次：

```
E:\Kaoyan\clawer\sync-now.bat
```

- 窗口会逐校显示 `Probe 清华大学... ok`
- 全部跑完约 **15–25 分钟**（官方无变化也要探测一遍）
- **不要中途关窗口**

### 方式二：自动

双击 **`start-scheduler.bat`**，保持窗口不关，每天 0:00 自动检测。

或用 Windows **任务计划程序**，每天 0:00 运行 `E:\Kaoyan\clawer\sync-now.bat`（更稳，不用开窗口）。

---

## 怎么知道成功了

### 1. 看黑窗口最后一行

**同步成功（官方无变化）：**

```
同步完成: 新增 0 | 删除 0 | 更新 0 | 无变化 147
官方数据无变化，本地文件未重写详情。
```

**同步成功（官方有更新）：**

```
同步完成: 新增 0 | 删除 0 | 更新 2 | 无变化 145
```

**全量抓取成功：**

```
=== Crawl finished OK: 147/147 schools ===
```

### 2. 看变更报告

打开（把日期换成当天）：

```
E:\Kaoyan\re\logs\changes-2026-06-15.json
```

看 `summary` 字段：

| 字段 | 含义 |
|------|------|
| `added` | 官方新增的双一流院校 |
| `removed` | 官方移除的院校 |
| `updated` | 有变化的院校（见下方 changes） |
| `unchanged` | 无变化，未重新下载 |

`updated` 里 `changes` 可能是：

- `overview` — 学校概况变了
- `plans` — 招生计划变了
- `scores` — 历年分数变了

### 3. 校验数据完整性

```bat
cd /d E:\Kaoyan\clawer
npm run verify
```

显示 **`结论: 数据完整，任务成功 ✓`** 即数据没问题。

---

## 数据存在哪里

```
E:\Kaoyan\re\
├── latest\
│   ├── schools.json              ← 147 所名单（简要信息）
│   └── syl-schools-full.json     ← 完整详情（概况+计划+分数，约 79MB）
├── manifest.json                 ← 指纹基准（用于对比是否变化）
├── history\YYYY-MM-DD\           ← 按日期归档的历史快照
└── logs\
    ├── YYYY-MM-DD.log            ← 运行日志
    └── changes-YYYY-MM-DD.json   ← 每日变更报告
```

### 每所学校的数据结构

在 `syl-schools-full.json` 里，每校包含：

```json
{
  "name": "清华大学",
  "overview": { "intro": "...", "rank": [...], "school_site": [...] },
  "plans": { "year": 2026, "total": 142, "items": [...] },
  "scores": { "years": { "2022": [...], "2023": [...], ... } }
}
```

---

## 命令行参考（可选）

在 `E:\Kaoyan\clawer` 目录下：

| 命令 | 说明 |
|------|------|
| `npm run sync` | 同 `sync-now.bat` |
| `npm run crawl` | 同 `crawl-now.bat`（全量） |
| `npm run crawl:list` | 只更新 147 所名单（约 10 秒） |
| `npm run manifest` | 重建指纹基准 |
| `npm run verify` | 校验数据 |
| `npm start` | 同 `start-scheduler.bat` |

强制从头全量重抓（忽略断点）：

```bat
node scripts/run-once.js --fresh
```

---

## 配置

编辑 `config.js` 可修改：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `outputDir` | `E:\Kaoyan\re` | 数据输出目录 |
| `planYear` | `2026` | 招生计划年份 |
| `scoreYears` | 2022–2026 | 历年分数年份 |
| `cronSchedule` | `0 0 * * *` | 定时（每天 0:00） |
| `timezone` | `Asia/Shanghai` | 北京时间 |

---

## 常见问题

**Q：双击 bat 闪退？**  
A：先双击 `install.bat`；或在 cmd 里 `cd E:\Kaoyan\clawer` 后运行对应命令看报错。

**Q：sync 要跑多久？**  
A：约 15–25 分钟，需保持窗口打开。

**Q：官方很久不更新还要跑吗？**  
A：可以隔几天跑一次；无变化时会提示 `unchanged: 147`，不会重写大文件。

**Q：数据备份在哪？**  
A：`E:\Kaoyan\data` 有一份手动备份；每日归档在 `E:\Kaoyan\re\history\`。

**Q：抓取失败怎么办？**  
A：再跑一次 `sync-now.bat`；仍失败则 `crawl-now.bat` 全量重抓，再 `npm run manifest`。

---

## 环境要求

- Windows 10/11
- Node.js >= 20
- 可访问 `kaoyan.cn` 的网络

数据仅供个人学习研究，请遵守掌上考研网站使用规范。

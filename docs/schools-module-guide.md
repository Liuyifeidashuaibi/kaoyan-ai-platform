# 择校模块 - 本地维护说明

择校数据**不在 GitHub 仓库**，由本机三个目录协作：

| 目录 | 作用 |
|------|------|
| E:\Kaoyan\clawer | 抓取掌上考研，写 JSON |
| E:\Kaoyan\re | 数据落地（latest\syl-schools-full.json） |
| 本项目 crawler/（本地，已 gitignore） | 读 
e → Supabase → 网站刷新 |

## 日常用法

| 场景 | 操作 |
|------|------|
| 每日自动（爬取 + 上网站） | clawer\daily-sync-and-publish.bat 或 start-scheduler.bat |
| 只爬数据（不上网站） | clawer\sync-now.bat |
| 只发布到网站 | 
pm run crawler:kaoyan:import 或 scripts\publish-schools.bat |

爬虫详细说明见 E:\Kaoyan\clawer\README.md，发布脚本说明见本地 crawler/README.md。

## 环境变量

`env
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
KAOYAN_DATA_DIR=E:\Kaoyan\re
`

## 常见问题

确认 E:\Kaoyan\re\latest\syl-schools-full.json 存在后再发布。

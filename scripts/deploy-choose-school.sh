#!/usr/bin/env bash

# 择校数据中心部署脚本

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"



echo "==> 安装爬虫依赖"

pip install -r "$ROOT/crawler/requirements.txt"



echo "==> 可选：Playwright 浏览器"

if command -v playwright &>/dev/null; then

  playwright install chromium || true

fi



echo "==> 创建原始数据目录"

mkdir -p "$ROOT/crawler/raw"



echo "==> 生成学校白名单"

cd "$ROOT/crawler"

python main.py build-whitelist



echo "==> 同步 school_sources 入口库"

python main.py seed-sources || true



echo ""

echo "==> 请在 Supabase 执行迁移（按顺序）："

echo "    supabase/migrations/007_choose_school_datacenter.sql"

echo "    supabase/migrations/009_admission_datacenter.sql"

echo ""

echo "==> 全量抓取:     python crawler/main.py full"

echo "==> 增量更新:     python crawler/main.py update"

echo "==> 统计重算:     python crawler/main.py recompute-stats"

echo "==> 后端 API:     cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo "==> 前端:         npm run dev  访问 /choose-school 或 /schools"

echo "部署准备完成。"


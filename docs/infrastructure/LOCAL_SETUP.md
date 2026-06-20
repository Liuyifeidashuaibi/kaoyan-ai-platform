# Redis + Celery 本地单机部署指南

面向 **4090 单机本地测试**，不含多机分布式逻辑。

## 目录结构（新增，与核心业务隔离）

```
backend/app/infrastructure/
├── cache/          # Redis 热点缓存（院校、分数线、AI 问答、翻译、会员额度）
└── tasks/          # Celery 异步任务（PDF/OCR/爬虫/RAG）

backend/app/routers/tasks.py   # 任务提交与状态查询 API（新增路由）

docker/
├── Dockerfile.backend
├── Dockerfile.frontend
├── Dockerfile.celery
└── redis.conf

docker-compose.yml             # 一键启动全部服务
examples/
├── test_redis_cache.py
└── test_celery_tasks.py
```

## 一、本机直跑（不用 Docker）

### 1. 安装 Redis（Windows）

推荐使用 WSL2 或 Memurai / Redis for Windows：

```powershell
# WSL Ubuntu 示例
sudo apt update && sudo apt install -y redis-server
sudo service redis-server start
redis-cli ping   # 应返回 PONG
```

### 2. Python 依赖

```powershell
cd backend
pip install -r requirements.txt
```

### 3. 环境变量（项目根 `.env`）

```env
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/1
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2

# 缓存 TTL（秒，均可选）
CACHE_TTL_SCHOOLS_LIST=1800
CACHE_TTL_SCORE_LINES=1800
CACHE_TTL_TRANSLATOR=86400
RESPONSE_CACHE_TTL_SECONDS=3600

# 会员额度（本地测试）
MEMBERSHIP_DAILY_TRANSLATE_LIMIT=50
MEMBERSHIP_DAILY_CHAT_LIMIT=200
```

### 4. 启动服务（4 个终端）

```powershell
# 终端 1 — Redis（若未作为系统服务运行）
redis-server

# 终端 2 — FastAPI
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 终端 3 — Celery Worker
cd backend
celery -A app.infrastructure.tasks.celery_app worker --loglevel=info -Q default,heavy

# 终端 4 — Celery Beat（定时分数线爬虫，可选）
cd backend
celery -A app.infrastructure.tasks.celery_app beat --loglevel=info

# 终端 5 — Next.js
npm run dev
```

访问 http://localhost:3000

## 二、Docker Compose 一键启动（推荐，无需多终端）

```powershell
cd E:\Kaoyan\kaoyan-ai-platform
.\scripts\start-all.ps1
```

含 Redis + 后端 + 前端 + Celery + **Translator**，全部后台容器。

关闭：`.\scripts\stop-all.ps1`

或手动：

```powershell
docker compose up -d --build
docker compose logs -f backend translator frontend
docker compose down
```

| 服务 | 端口 |
|------|------|
| frontend | 3000 |
| backend | 8000 |
| translator | 8100 |
| redis | 6379 |

翻译依赖本机 **Ollama**（11434，GPU）；`.env` 配置 `TRANSLATOR_ROOT=E:/Tanslator/translatorai`。

## 三、Redis 缓存说明

| 缓存项 | Key 前缀 | 默认 TTL |
|--------|----------|----------|
| 院校列表/详情 | `kaoyan:schools:` | 30~60 分钟 |
| 复试分数线 | `kaoyan:score_lines:` | 30 分钟 |
| 重复 AI 问答 | `kaoyan:chat_qa:` | 3600 秒 |
| 双语翻译结果 | `kaoyan:translator:` | 24 小时 |
| 用户会员额度 | `kaoyan:membership:` | 至当日 UTC 午夜 |

Redis 不可用时 **自动降级** 为内存/直查数据库，不影响原有接口。

## 四、Celery 异步任务 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/tasks/pdf/parse` | 上传 PDF，立即返回 task_id |
| POST | `/api/tasks/ocr/batch` | 批量图片 OCR |
| POST | `/api/tasks/rag/ingest` | RAG 向量化（form: source, force） |
| POST | `/api/tasks/crawler/scores` | 手动触发分数线爬虫 |
| GET | `/api/tasks/{task_id}` | 查询进度 |
| GET | `/api/tasks` | 当前用户任务列表 |
| GET | `/api/tasks/quota` | 会员额度 |
| GET | `/api/tasks/health` | Redis/Celery 状态 |

**原有同步接口不变**（chat、translator、schools 等仍可直接调用）。

### 前端轮询示例

```typescript
import { fetchTaskStatus } from "@/lib/api/tasks";

const { task_id } = await submitPdfParse(file);
const poll = setInterval(async () => {
  const task = await fetchTaskStatus(task_id);
  if (task.status === "done" || task.status === "failed") clearInterval(poll);
}, 2000);
```

## 五、测试脚本

```powershell
# Redis 缓存
python examples/test_redis_cache.py

# Celery 任务（需 Redis + Worker 运行中）
python examples/test_celery_tasks.py
```

## 六、4090 GPU 说明

- Celery Worker 默认 `--concurrency=2`，避免 GPU 任务堆积
- OCR/向量化走 DashScope 云端 API，本地 GPU 主要用于 Translator 独立服务
- 若 Translator 也容器化并需 GPU，在 `docker-compose.yml` 底部取消 nvidia 注释

## 七、缓存失效

- 定时爬虫任务完成后自动清除 `kaoyan:schools:*` 与 `kaoyan:score_lines:*`
- 手动: `redis-cli KEYS "kaoyan:schools:*" | xargs redis-cli DEL`

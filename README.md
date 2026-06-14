# 考研 AI 平台

面向考研备考的 AI 学习平台：智能答疑、错题本、择校数据、社区交流。

## 功能模块

| 模块 | 说明 | 数据存储 |
|------|------|----------|
| **AI 聊天** | 流式对话、图片 OCR、RAG 知识库 | 后端 SQLite |
| **错题本** | 多类型资料上传、AI 解析、公开/隐私 | 后端 SQLite + 本地文件 |
| **择校** | 院校/专业/分数线查询 | Supabase |
| **社区** | 发帖、收藏、关注、个人主页 | Supabase |
| **番茄钟** | 本地专注计时 | 浏览器 localStorage |

## 架构

```
浏览器 → Vercel (Next.js 16)
           ├─ Supabase Auth（登录）
           └─ /api/* 代理 → Render / 本地 FastAPI
                  ├─ SQLite（聊天、错题本）
                  ├─ uploads/ + Chroma（文件与向量）
                  └─ Supabase Postgres（社区、择校）
```

## 本地开发

### 1. 环境变量

```bash
cp .env.example .env.local
# 填写 DASHSCOPE_API_KEY、Supabase 等（可参考 crawler/.env）
```

### 2. 启动服务

```bash
# 前端
npm install
npm run dev

# 后端（另开终端）
cd backend
pip install -r requirements.txt
cd ..
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

访问 http://localhost:3000

### 3. 数据库迁移（社区模块）

```bash
npm run db:migrate:013
```

## 部署

完整步骤见 **[DEPLOY.md](./DEPLOY.md)**：

- **前端**：GitHub → Vercel 自动部署
- **后端**：Render Blueprint（`render.yaml` + `Dockerfile`）
- **数据库**：Supabase 迁移脚本在 `supabase/migrations/`

### Vercel 环境变量（必填）

| 变量 | 说明 |
|------|------|
| `BACKEND_URL` | Render 后端地址 |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase 项目 URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |

### Render 环境变量（必填）

| 变量 | 说明 |
|------|------|
| `DASHSCOPE_API_KEY` | 千问 API Key |
| `SUPABASE_URL` | 社区/择校 |
| `SUPABASE_SERVICE_ROLE_KEY` | 后端读写 Supabase |
| `CORS_ORIGINS` | 含 Vercel 域名 |

## 脚本

```bash
npm run dev          # 开发服务器
npm run build        # 生产构建
npm run lint         # ESLint
npm run typecheck    # TypeScript 检查
npm run db:migrate:013  # 社区表迁移
```

## 已知限制（后续迭代）

- 聊天会话尚未按用户隔离（单后端实例共享 SQLite）
- Render 免费实例磁盘不持久，错题本/聊天数据重启可能丢失
- 生产环境建议为聊天/错题本接入 Postgres 与对象存储

## 仓库

https://github.com/Liuyifeidashuaibi/kaoyan-ai-platform

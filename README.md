# 考研 AI 平台

面向考研备考的 AI 学习平台：智能答疑、错题本、择校数据、社区交流。

## 功能模块

| 模块 | 说明 | 数据存储 |
|------|------|----------|
| **AI 聊天** | 流式对话、图片 OCR、RAG 知识库 | 后端 SQLite |
| **错题本** | 多类型资料上传、AI 解析、公开/隐私 | 后端 SQLite + 本地文件 |
| **择校** | 院校/专业/分数线查询（147 所双一流） | Supabase |
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

## 部署（无 Render）

**不需要 Render。** 推荐：**Vercel 托管前端**，**本机跑 FastAPI**，用 **Cloudflare Tunnel** 暴露给 Vercel。

```
Vercel 前端  →  BACKEND_URL  →  Cloudflare Tunnel  →  你电脑上的 :8000
```

### 最快试通（无自有域名，约 5 分钟）

**1. Vercel 环境变量**（Settings → Environment Variables）：

| 变量 | 说明 |
|------|------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `BACKEND_URL` | 见第 3 步隧道地址 |
| `NEXT_PUBLIC_API_URL` | 与 `BACKEND_URL` 相同（聊天流式建议必配） |

**2. 本机启动后端 + 临时隧道**（项目根目录 PowerShell）：

```powershell
.\scripts\start-local-stack.ps1
```

若没有 `cloudflare-tunnel/config.yml`，会自动用**临时隧道**，窗口里会出现类似：

`https://xxxx.trycloudflare.com`

**3.** 把该地址填进 Vercel 的 `BACKEND_URL` 和 `NEXT_PUBLIC_API_URL`，然后 **Redeploy**。

**4.** 本机 `.env` 需有 `DASHSCOPE_API_KEY`；`CORS_ORIGINS` 要包含你的 Vercel 域名，例如：

```env
CORS_ORIGINS=http://localhost:3000,https://kaoyan-ai-platform.vercel.app
```

**5.** 验证：`https://你的vercel域名/api/backend-health` 返回 `success: true`

> 临时隧道 URL **每次重启会变**，需重新改 Vercel 并 Redeploy。  
> 有 Cloudflare 域名时，见 [DEPLOY.md](./DEPLOY.md) 配置**固定域名**（改一次即可）。

### 社区模块

```bash
npm run db:migrate:013
```

后端 `.env` 还需：`SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`

---

## 部署（可选：Render 云后端）

若不想本机常开，可用 Render 部署后端，见 **[DEPLOY.md](./DEPLOY.md)** 第一节。

## 脚本

```bash
npm run dev          # 开发服务器
npm run build        # 生产构建
npm run lint         # ESLint
npm run typecheck    # TypeScript 检查
npm run db:migrate:013  # 社区表迁移
npm run crawler:kaoyan:sync   # 掌上考研增量同步 + 导入
npm run crawler:kaoyan:import # 仅导入已有 JSON 到 Supabase
```

择校模块完整说明：[docs/schools-module-guide.md](./docs/schools-module-guide.md)

## 已知限制（后续迭代）

- 聊天会话尚未按用户隔离（单后端实例共享 SQLite）
- Render 免费实例磁盘不持久，错题本/聊天数据重启可能丢失
- 生产环境建议为聊天/错题本接入 Postgres 与对象存储

## 仓库

https://github.com/Liuyifeidashuaibi/kaoyan-ai-platform

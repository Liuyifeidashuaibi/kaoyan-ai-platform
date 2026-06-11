# 部署指南 — 考研 AI 平台

Vercel 只托管 **Next.js 前端**。AI 聊天与错题本依赖 **FastAPI 后端**（千问 API），需单独部署。

## 架构

```
浏览器 → Vercel (Next.js) → 代理 /api/chat、/api/wrong-questions → Render/Railway (FastAPI)
         ↓
      Supabase 登录
```

## 一、部署后端（Render 推荐）

1. 将代码推送到 GitHub
2. 打开 [Render](https://render.com) → **New Blueprint** → 选择本仓库（使用根目录 `render.yaml`）
3. 在 Render 环境变量中设置：
   - `DASHSCOPE_API_KEY` = 你的千问 API Key
   - `PUBLIC_BASE_URL` = `https://你的-render-服务.onrender.com`（**图片问答必配**，供 qwen2.5-vl 拉取 `/uploads` 图片）
   - `LLM_MODEL` = `qwen-max-latest`（默认已在 render.yaml）
   - `VL_MODEL` = `qwen2.5-vl-72b-instruct`（预算不足可改为 `qwen2.5-vl-7b-instruct`）
   - `CORS_ORIGINS` = `https://kaoyan-ai-platform.vercel.app,http://localhost:3000`
4. 部署完成后记下 URL，例如 `https://kaoyan-ai-api.onrender.com`

本地测试后端：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 二、配置 Vercel 环境变量

在 [Vercel 项目 Settings → Environment Variables](https://vercel.com) 添加：

| 变量 | 值 |
|------|-----|
| `BACKEND_URL` | `https://你的-render-服务.onrender.com` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `DASHSCOPE_API_KEY` | 仅后端需要；Vercel 可不填 |

可选：若 SSE 流式在代理下超时，可额外设置  
`NEXT_PUBLIC_API_URL=https://你的-render-服务.onrender.com`（浏览器直连后端）。

## 三、推送前端代码

确保以下目录已提交并 push 到 GitHub，Vercel 会自动重新部署：

- `src/components/chat/`
- `src/components/wrong-questions/`
- `src/lib/api/`
- `backend/`
- `next.config.ts`（API 代理）

## 四、验证

1. 打开 `https://kaoyan-ai-platform.vercel.app`
2. 登录后进入 **AI 聊天** / **错题本**
3. 检查 `https://你的域名/api/backend-health` 应返回 `success: true`

本地开发：先启动后端 `uvicorn`，再 `npm run dev`，访问 http://localhost:3000
